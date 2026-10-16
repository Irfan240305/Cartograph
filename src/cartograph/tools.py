from dataclasses import dataclass

import os
from pathlib import Path

from typing import Annotated

from langchain.tools import tool, ToolRuntime

from langgraph.types import interrupt
import numpy as np

import psycopg
from pgvector.psycopg import register_vector

from cartograph.llm import get_embedder

import json

from cartograph.guards import make_safe

@dataclass
class Context:
  repo_path:str

MAX_FILE_LINES=300
MAX_LIST_ENTRIES=100
MAX_SEARCH_MATCHES=20
IGNORED_DIRS={".git", ".venv", "node_modules", "__pycache__", "target"}

def safe_path(repo_path: str, user_path:str) -> Path | None:
  """Return the real path if it is stays inside the project, otherwise None."""
  repo = Path(repo_path).resolve()
  target = (repo / user_path).resolve()

  if target.is_relative_to(repo):
    return target
  return None


##never read secret files, even inside the project

def is_secret(path: Path) -> bool:
  """True if the file is a secret file, otherwise False."""
  return path.name.startswith(".env") and path.name != ".env.example"


@tool
def read_file(
  path: Annotated[str, "File path inside the project, like 'src/App.java'"],
  runtime:ToolRuntime[Context]
) -> str:

  """Read a file from the project. Use this after search_code or list_files to see the actual code before answering."""

  file = safe_path(runtime.context.repo_path , path)
  if file is None:
    return f"Error: The file '{path}' is outside the project."
  if is_secret(file):
    return f"Error: The file '{path}' is a secret file and cannot be read."
  if not file.is_file():
     return f"Error: '{path}' is not a file. Use list_files or search_code to find the correct path."

  lines = file.read_text(encoding="utf-8", errors="ignore").splitlines()
  shown =  "\n".join(lines[:MAX_FILE_LINES])

  if len(lines) > MAX_FILE_LINES:
    shown += f"\n\n[Cut at line {MAX_FILE_LINES} of {len(lines)}]"

  return make_safe(shown)

@tool
def list_files(
  runtime : ToolRuntime[Context],
  folder : Annotated[str | None, "Folder inside the project, like 'src'. Use '.' for the top level"] = ".",

) -> str:
  """List the files and folders inside the project folder. Use this to understand the project's structure."""
  folder = folder or "."
  repo = Path(runtime.context.repo_path).resolve()
  base = safe_path(runtime.context.repo_path, folder)
  if base is None:
    return f"Error: The folder '{folder}' is outside the project."
  if not base.is_dir():
    return f"Error: '{folder}' is not a folder. Use list_files with '.' to list the top-level folders."

  entries = []
  for item in sorted(base.iterdir()):
    if item.name in IGNORED_DIRS:
      continue
    relative = item.relative_to(repo).as_posix()

    if item.is_dir():
      entries.append(relative + "/")
    else:
      entries.append(relative)

  if not entries:
    return f"Error: The folder '{folder}' is empty."
  shown = "\n".join(entries[:MAX_LIST_ENTRIES])

  if len(entries) > MAX_LIST_ENTRIES:
    shown += f"\n\n[Cut at {MAX_LIST_ENTRIES} entries of {len(entries)}]"
  return shown


@tool
def search_code(
  text: Annotated[str, "Word or name to search for like 'login' or 'AuthService'"],
  runtime : ToolRuntime[Context],
) -> str:
  """Find which files contain the given text, with line numbers. Use this first to locate where something is defined or used."""

  repo = Path(runtime.context.repo_path).resolve()
  matches = []
  for file in repo.rglob("*"):
    relative = file.relative_to(repo)
    if any(part in IGNORED_DIRS for part in relative.parts):
      continue
    if not file.is_file():
      continue
    if is_secret(file):
      continue

    lines = file.read_text(encoding="utf-8", errors="ignore").splitlines()
    for number, line in enumerate(lines, start=1):
      if text.lower() in line.lower():
        matches.append(f"{relative.as_posix()}:{number}: {line.strip()[:120]}")
  if not matches:
      return f"No matches found for '{text}' in the project."
  shown = "\n".join(matches[:MAX_SEARCH_MATCHES])
  if len(matches) >= MAX_SEARCH_MATCHES:
          
      shown += f"\n\n[Showing {MAX_SEARCH_MATCHES} of {len(matches)} matches. Try a more specific word.]"
  return make_safe(shown)

@tool
def ask_user(question: Annotated[str, "A short clarifying question for the user"]):
  """Ask only when the user question is unclear or ambiguous."""
  reply = interrupt({"question": question})
  return reply["data"]

@tool
def semantic_search(
  query: Annotated[str, "Describe what you're looking for in plain words, like 'how secret files are protected'"],
) -> str:
  """Find code by MEANING, even when you don't know the exact names or words used in the code. Use this first for 'how does X work' or 'where is X handled' questions."""
  try:

    query_vector = get_embedder().embed_query(query)

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
      register_vector(conn)
      rows = conn.execute(
        "SELECT path, start_line, end_line, content FROM chunks ORDER BY embedding <=> %s LIMIT 5",
        (np.array(query_vector),),  
      ).fetchall()
  except Exception as e:
    return f"Error: semantic search unavailable ({e.__class__.__name__}). Try keyword_search or find_symbol instead."
  

  if not rows:
    return "No indexed code are found. Run index.py to index the project first"
    
    
  results=[]

  for row in rows:
    path, start_line, end_line, content = row
    results.append(f"{path}:{start_line}-{end_line}: {content[:600]}")

  return make_safe("\n\n---\n\n".join(results))


@tool 
def navigate_repo(runtime: ToolRuntime[Context]) -> str:
  """Show the project map: every folder and file with a one-line summary. Use this FIRST for broad or architecture questions, or when you don't know which file holds something."""
  map_file = Path(runtime.context.repo_path).resolve() / "data" / "repo_map.json"
  if not map_file.is_file():
    return "No project map found. Run build_summarized_map first."
  tree = json.loads(map_file.read_text(encoding="utf-8"))
  return "\n".join(map_to_lines(tree))

@tool
def find_symbol(
  name: Annotated[str, "Exact function or class name, like 'safe_path' or 'CodeAnswer'"],
) -> str:
  """Find exactly where a function or class is defined (file and line). Use this when you know the name."""
  try:
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
      rows = conn.execute(
        "SELECT kind, name, path, line FROM symbols WHERE name = %s",
        (name,),
      ).fetchall()
      if not rows:
        rows = conn.execute(
          "SELECT kind, name, path, line FROM symbols WHERE name ILIKE %s LIMIT 10",
          (f"%{name}%",),
        ).fetchall()
  except Exception as e:
    return f"Error: symbol search unavailable ({e.__class__.__name__}). Try keyword_search or semantic_search instead."

  if not rows:
    return f"No symbols found for '{name}' in the project. Try search_code or semantic_search instead."
  return "\n".join(f"{kind} {sym} → {path}:{line}" for kind, sym, path, line in rows)

def keyword_rows(query: str, limit: int = 10) -> list[tuple]:
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:

      return conn.execute(

        """
        SELECT id, path, start_line, end_line, content
        FROM chunks, to_tsquery('english', replace(plainto_tsquery('english', %s)::text, '&', '|')) AS q
        WHERE search_words @@ q
        ORDER BY ts_rank(search_words, q) DESC
        LIMIT %s
        """,
        (query, limit),
        ).fetchall()

def semantic_rows(query: str, limit: int = 10) -> list[tuple]:
    query_vector = get_embedder().embed_query(query)
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
      register_vector(conn)
      return conn.execute(
        "SELECT id, path, start_line, end_line, content FROM chunks ORDER BY embedding <=> %s LIMIT %s",
        (np.array(query_vector), limit),
        ).fetchall()
    
def rrf_merge(list1: list[tuple], list2: list[tuple], k: int = 60) -> list[tuple]:
  scores = {}
  rows = {}
  for result_list in (list1, list2):
    for place, row in enumerate(result_list, start=1):
      chunk_id = row[0]
      scores[chunk_id] = scores.get(chunk_id, 0) + 1 / (k + place)
      rows[chunk_id] = row
  best_ids = sorted(scores, key=scores.get, reverse=True)
  return [rows[chunk_id] for chunk_id in best_ids]


@tool
def hybrid_search(
  query: Annotated[str, "What you're looking for, in plain words or exact terms"],
) -> str:
  """Best general code search: combines keyword and meaning search, so it finds code by exact words AND by what it does. Use this as your default search."""
  try:
    keyword_list = keyword_rows(query)
  except Exception:
    keyword_list = []

  try:
    semantic_list = semantic_rows(query)
  except Exception:
    semantic_list = []

  if not keyword_list and not semantic_list:
    return "Error: search unavailable or nothing indexed. Try search_code or list_files instead."

  merged = rrf_merge(keyword_list, semantic_list)[:5]
  results = []
  for _id, path, start_line, end_line, content in merged:
    results.append(f"{path} (lines {start_line}-{end_line}):\n{content[:600]}")
  return make_safe("\n\n---\n\n".join(results))


@tool
def keyword_search(
  query: Annotated[str, "Words to search for, like 'rate limit retry' or 'secret env file'"],
) -> str:
  """Find code chunks containing these WORDS, best matches first. Use this for exact terms, error codes, or config names."""
  try:
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
      rows = conn.execute(
        """
        SELECT path, start_line, end_line, content
        FROM chunks, websearch_to_tsquery('english', %s) AS q
        WHERE search_words @@ q
        ORDER BY ts_rank(search_words, q) DESC
        LIMIT 5
        """,
        (query,),
      ).fetchall()
  except Exception as e:
    return f"Error: keyword search unavailable ({e.__class__.__name__}). Try semantic_search or search_code instead."

  if not rows:
    return f"No code chunks found for '{query}' in the project. Try search_code or semantic_search instead."

  results = []
  for path, start_line, end_line, content in rows:
    results.append(f"{path} (lines {start_line}-{end_line}):\n{content[:600]}")
  return make_safe("\n\n---\n\n".join(results))

def map_to_lines(node: dict, depth: int=0) -> list[str]:
    indent = "  " * depth
    lines = [f"{indent}{node['name']} — {node.get('summary', '')}"]
    for child in node.get("children", []):
      lines.extend(map_to_lines(child, depth + 1))

    return lines

ALL_TOOLS = [list_files, search_code, read_file, ask_user, semantic_search, navigate_repo, find_symbol, keyword_search, hybrid_search]