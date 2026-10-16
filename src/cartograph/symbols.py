import ast
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

from cartograph.indexer import code_files

load_dotenv(override=True)


def extract_symbols(file: Path, repo: Path) -> list[dict]:
  try:
    tree = ast.parse(file.read_text(encoding="utf-8", errors="ignore"))
  except SyntaxError:
    return []

  symbols = []
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
  # Never erase everything; create the notebook only once, with a sticker column
  conn.execute("""
    CREATE TABLE IF NOT EXISTS symbols (
      id SERIAL PRIMARY KEY,
      repo_id TEXT NOT NULL,
      name TEXT NOT NULL,
      kind TEXT NOT NULL,
      path TEXT NOT NULL,
      line INT NOT NULL
    )
  """)
  conn.execute("CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols (name)")
  conn.execute("CREATE INDEX IF NOT EXISTS idx_symbols_repo ON symbols (repo_id)")


def index_symbols(repo_path: str, repo_id: str) -> int:
  repo = Path(repo_path).resolve()
  symbols = []
  for file in code_files(repo_path):
    if file.suffix == ".py":
      symbols.extend(extract_symbols(file, repo))

  with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
    create_symbols_table(conn)
    # Erase only THIS project's old symbols
    conn.execute("DELETE FROM symbols WHERE repo_id = %s", (repo_id,))
    with conn.cursor() as cur:
      # Write the sticker on every symbol
      cur.executemany(
        "INSERT INTO symbols (repo_id, name, kind, path, line) VALUES (%s, %s, %s, %s, %s)",
        [(repo_id, s["name"], s["kind"], s["path"], s["line"]) for s in symbols],
      )
  return len(symbols)