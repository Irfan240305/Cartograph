import os
from pathlib import Path

import numpy as np
import psycopg
from dotenv import load_dotenv
from langchain_text_splitters import Language, RecursiveCharacterTextSplitter
from pgvector.psycopg import register_vector

from cartograph.llm import get_embedder
from cartograph.tools import IGNORED_DIRS, is_secret

import time

import uuid

import hashlib

import logging

logger = logging.getLogger(__name__)

load_dotenv(override=True)

CODE_EXTENSIONS = {".py", ".java", ".md", ".toml", ".js", ".ts"}


def code_files(repo_path: str) -> list[Path]:
  repo = Path(repo_path).resolve()
  files = []
  for file in repo.rglob("*"):
    relative = file.relative_to(repo)
    if any(part in IGNORED_DIRS for part in relative.parts):
      continue
    if not file.is_file():
      continue
    if file.suffix not in CODE_EXTENSIONS:
      continue
    if is_secret(file):
      continue

    if file.stat().st_size > 1 * 1024 * 1024:  # 1 MB
       logger.warning("Skipping oversized file: %s", relative)
       continue

    files.append(file)
  return files


LANGUAGES = {
  ".py": Language.PYTHON,
  ".java": Language.JAVA,
  ".js": Language.JS,
  ".ts": Language.TS,
  ".md": Language.MARKDOWN,
}
CHUNK_SIZE = 1500


def make_splitter(suffix: str):
  language = LANGUAGES.get(suffix)
  if language:
    return RecursiveCharacterTextSplitter.from_language(
      language, chunk_size=CHUNK_SIZE, chunk_overlap=200, add_start_index=True
    )
  return RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=200, add_start_index=True)


def chunk_file(file: Path, repo: Path) -> list[dict]:
  text = file.read_text(encoding="utf-8", errors="ignore")
  splitter = make_splitter(file.suffix)
  chunks = []
  for doc in splitter.create_documents([text]):
    start = doc.metadata["start_index"]
    start_line = text[:start].count("\n") + 1
    end_line = start_line + doc.page_content.count("\n")
    chunks.append({
      "path": file.relative_to(repo).as_posix(),
      "start_line": start_line,
      "end_line": end_line,
      "text": doc.page_content,
    })
  return chunks

BATCH_SIZE = 100


def embed_texts(texts: list[str]) -> list[list[float]]:
    embedder = get_embedder()
    vectors = []

    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i:i + BATCH_SIZE]

        for attempt in range(4):
            try:
                batch_vectors = embedder.embed_documents(batch)

                if len(batch_vectors) != len(batch):
                    raise ValueError(
                        "Embedding count does not match batch size."
                    )

                vectors.extend(batch_vectors)
                break

            except Exception as e:
                error = str(e).lower()

                quota_error = (
                    "resource_exhausted" in error
                    or "quota" in error
                    or "429" in error
                )

                if quota_error:
                    raise RuntimeError(
                        "Embedding quota limit reached. "
                        "Check your Gemini quota and retry later."
                    ) from e

                if attempt == 3:
                    raise

                wait_seconds = 2 ** (attempt + 1)
                print(
                    f"Embedding request failed. Retrying in "
                    f"{wait_seconds}s (attempt {attempt + 1}/4)."
                )
                time.sleep(wait_seconds)

    return vectors


def create_table(conn, dimensions: int):
  # Change 1: never erase everything; create the notebook only once
  # Change 2: every note has a sticker (repo_id)
  conn.execute(f"""
    CREATE TABLE IF NOT EXISTS chunks (
      id SERIAL PRIMARY KEY,
      repo_id TEXT NOT NULL,
      path TEXT NOT NULL,
      start_line INT NOT NULL,
      end_line INT NOT NULL,
      content TEXT NOT NULL,
      embedding VECTOR({dimensions}) NOT NULL,
      search_words TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', content)) STORED
    )
  """)
  conn.execute("CREATE INDEX IF NOT EXISTS chunks_words ON chunks USING GIN (search_words)")
  conn.execute("CREATE INDEX IF NOT EXISTS chunks_repo ON chunks (repo_id)")




def index_repo(repo_path: str, repo_id: str) -> int:
    repo = Path(repo_path).resolve()

    # Step 1: Scan and chunk the repository.
    chunks = []
    for file in code_files(str(repo)):
        chunks.extend(chunk_file(file, repo))

    if not chunks:
        return 0

    # Step 2: Create a stable ID for this exact repository snapshot.
    # The same unchanged repository will get the same staging ID on retry.
    snapshot = hashlib.sha256()
    for chunk in chunks:
        snapshot.update(chunk["path"].encode("utf-8"))
        snapshot.update(str(chunk["start_line"]).encode("utf-8"))
        snapshot.update(str(chunk["end_line"]).encode("utf-8"))
        snapshot.update(chunk["text"].encode("utf-8"))

    staging_id = f"{repo_id}__staging__{snapshot.hexdigest()[:16]}"

    # Step 3: Find chunks already saved by a previous attempt.
    rows = []

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        table_exists = conn.execute(
            "SELECT to_regclass('public.chunks')"
        ).fetchone()[0] is not None

        if table_exists:
            rows = conn.execute(
                """
                SELECT path, start_line, end_line, content
                FROM chunks
                WHERE repo_id = %s
                """,
                (staging_id,),
            ).fetchall()
            

    existing_keys = set(rows)

    pending = [
        chunk for chunk in chunks
        if (
            chunk["path"],
            chunk["start_line"],
            chunk["end_line"],
            chunk["text"],
        ) not in existing_keys
    ]

    logger.info(
       "Chunk indexing status: total=%d, already_saved=%d, remaining=%d",
       len(chunks),
       len(existing_keys),
       len(pending)
    )

    # Step 4: Embed and save only missing chunks.
    # If an error occurs, keep saved staging chunks for a retry.
    for i in range(0, len(pending), BATCH_SIZE):
        batch = pending[i:i + BATCH_SIZE]
        vectors = embed_texts([chunk["text"] for chunk in batch])

        with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
            register_vector(conn)
            create_table(conn, len(vectors[0]))

            conn.cursor().executemany(
                """
                INSERT INTO chunks
                    (repo_id, path, start_line, end_line, content, embedding)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                [
                    (
                        staging_id,
                        chunk["path"],
                        chunk["start_line"],
                        chunk["end_line"],
                        chunk["text"],
                        np.array(vector),
                    )
                    for chunk, vector in zip(batch, vectors)
                ],
            )

        logger.info(
           "Saved %d of %d pending chunks",
           min(i + len(batch), len(pending)),
           len(pending),
        )

    # Step 5: Activate the completed snapshot in one transaction.
    # Existing active data remains untouched until this point.
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        conn.execute(
            "DELETE FROM chunks WHERE repo_id = %s",
            (repo_id,),
        )
        conn.execute(
            "UPDATE chunks SET repo_id = %s WHERE repo_id = %s",
            (repo_id, staging_id),
        )

    return len(chunks)
