import ast

from pathlib import Path


import os

import psycopg
from dotenv import load_dotenv

from cartograph.indexer import code_files

load_dotenv(override=True)

def extract_symbols(file : Path, repo: Path) -> list[dict]:
  try:
    tree = ast.parse(file.read_text(encoding="utf-8", errors="ignore"))
  except SyntaxError:
    return []

  symbols=[]
  path = file.relative_to(repo).as_posix()
  for node in ast.walk(tree):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
      kind = "function"
    elif isinstance(node, ast.ClassDef):
      kind = "class"
    else:
      continue
    symbols.append({
      "name": node.name,
      "kind": kind,
      "path": path,
      "line": node.lineno,
    })
  return symbols

def create_symbols_table(conn) -> None:
    conn.execute("DROP TABLE IF EXISTS symbols")
    conn.execute("""

    CREATE TABLE symbols (
      id SERIAL PRIMARY KEY,
      name TEXT NOT NULL,
      kind TEXT NOT NULL,
      path TEXT NOT NULL,
      line INT NOT NULL
    )
  """)
    conn.execute("CREATE INDEX idx_symbols_name ON symbols(name)")


def index_symbols(repo_path: str) -> int:
  repo = Path(repo_path).resolve()
  symbols=[]
  for file in code_files(repo_path):
    if file.suffix == ".py":
      symbols.extend(extract_symbols(file, repo))

  with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
    create_symbols_table(conn)

    with conn.cursor() as cur:
      cur.executemany(
        "INSERT INTO symbols (name, kind, path, line) VALUES (%s, %s, %s, %s)",
        [(s["name"], s["kind"], s["path"], s["line"]) for s in symbols]
      )
  return len(symbols)