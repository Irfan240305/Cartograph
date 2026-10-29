
import os
import logging
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from tree_sitter_language_pack import get_parser

from cartograph.indexer import code_files

logger = logging.getLogger(__name__)

load_dotenv(override=True)


PARSER_LANGUAGES = {
    ".py": "python",
    ".java": "java",
    ".js": "javascript",
    ".ts": "typescript",
}


def extract_symbols(file: Path, repo: Path) -> list[dict]:
    language = PARSER_LANGUAGES.get(file.suffix.lower())
    if language is None:
        return []

    try:
        source = file.read_bytes()
        parser = get_parser(language)
        tree = parser.parse(source)
    except (OSError, ValueError) as exc:
        logger.warning("Could not parse %s: %s", file, exc)
        return []

    symbols = []
    relative_path = file.relative_to(repo).as_posix()

    symbol_node_types = {
        "function_definition": "function",
        "class_definition": "class",
        "method_declaration": "function",
        "class_declaration": "class",
        "function_declaration": "function",
        "method_definition": "function",
    }

    def visit(node):
        kind = symbol_node_types.get(node.type)

        if kind:
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                name = source[name_node.start_byte:name_node.end_byte].decode(
                    "utf-8", errors="replace"
                )
                symbols.append({
                    "name": name,
                    "kind": kind,
                    "path": relative_path,
                    "line": node.start_point.row + 1,
                })

        for child in node.children:
            visit(child)

    visit(tree.root_node)
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
    if file.suffix.lower() in PARSER_LANGUAGES:
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