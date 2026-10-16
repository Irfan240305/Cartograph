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


BATCH_SIZE = 50

def embed_texts(texts: list[str]) -> list[list[float]]:
  embedder = get_embedder()
  vectors = []
  for i in range(0, len(texts), BATCH_SIZE):
    batch = texts[i:i + BATCH_SIZE]
    for attempt in range(5):
      try:
        vectors.extend(embedder.embed_documents(batch))
        break
      except Exception as e:
        if "RESOURCE_EXHAUSTED" not in str(e) or attempt == 4:
          raise
        print(f"Embedding limit reached ({len(vectors)}/{len(texts)} done). Waiting 60s...")
        time.sleep(60)
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
  chunks = []
  for file in code_files(repo_path):
    chunks.extend(chunk_file(file, repo))

  if not chunks:
    return 0

  texts = [c["text"] for c in chunks]
  vectors = embed_texts(texts)

  with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
    register_vector(conn)
    create_table(conn, len(vectors[0]))
    # Change 4: erase only THIS project's old notes
    conn.execute("DELETE FROM chunks WHERE repo_id = %s", (repo_id,))
    with conn.cursor() as cur:
      # Change 3: write the sticker on every note
      cur.executemany(
        "INSERT INTO chunks (repo_id, path, start_line, end_line, content, embedding) VALUES (%s, %s, %s, %s, %s, %s)",
        [(repo_id, c["path"], c["start_line"], c["end_line"], c["text"], np.array(v)) for c, v in zip(chunks, vectors)],
      )

  return len(chunks)