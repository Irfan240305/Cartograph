import os
from pathlib import Path

from cartograph.tools import IGNORED_DIRS, is_secret

from langchain_text_splitters import Language, RecursiveCharacterTextSplitter

from cartograph.llm import get_embedder

import numpy as np
import psycopg
from dotenv import load_dotenv
from pgvector.psycopg import register_vector

load_dotenv(override=True)

CODE_EXTENSIONS = {".py", ".java", ".md", ".toml", ".js", ".ts"}

def code_files(repo_path : str) -> list[Path]:
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


def chunk_file(file : Path, repo : Path) -> list[dict]:
    text = file.read_text(encoding="utf-8", errors="ignore")
    splitter = make_splitter(file.suffix)
    chunks = []
    for doc in splitter.create_documents([text]):
      start = doc.metadata["start_index"]
      start_line = text[:start].count("\n")+1
      end_line = start_line + doc.page_content.count("\n")

      chunks.append({
      "path": file.relative_to(repo).as_posix(),
      "start_line": start_line,
      "end_line": end_line,
      "text": doc.page_content,
      })
    return chunks


##embeddings

BATCH_SIZE = 50

def embed_texts(texts: list[str]) -> list[list[float]]:
  embedder = get_embedder()
  vectors = []
  for i in range(0, len(texts), BATCH_SIZE):
    batch = texts[i:i + BATCH_SIZE]
    vectors.extend(embedder.embed_documents(batch))
  return vectors

##Indexing
def create_table(conn, dimensions: int):
  conn.execute("DROP TABLE IF EXISTS chunks")
  conn.execute(f"""
    CREATE TABLE chunks (
      id SERIAL PRIMARY KEY,
      path TEXT NOT NULL,
      start_line INT NOT NULL,
      end_line INT NOT NULL,
      content TEXT NOT NULL,

      embedding VECTOR({dimensions}) NOT NULL,
      search_words TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', content)) STORED
    )
  """)
  conn.execute("CREATE INDEX ON chunks using GIN (search_words)")
def index_repo(repo_path : str) -> int:

  repo = Path(repo_path).resolve()
  chunks=[]
  for file in code_files(repo_path):
    chunks.extend(chunk_file(file, repo))

  if not chunks:
    return 0

  texts = [c["text"] for c in chunks]
  vectors = embed_texts(texts)

  with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
    register_vector(conn)
    create_table(conn, len(vectors[0]))
    with conn.cursor() as cur:
      cur.executemany(
        "INSERT INTO chunks (path, start_line, end_line, content, embedding) VALUES (%s, %s, %s, %s, %s)",
        [(c["path"], c["start_line"], c["end_line"], c["text"], np.array(v)) for c, v in zip(chunks, vectors)],
      )


  return len(chunks)
