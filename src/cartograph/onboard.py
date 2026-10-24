import os

import psycopg

from cartograph.indexer import index_repo
from cartograph.repomap import build_summarized_map
from cartograph.repos import clone_repo, parse_github_url, repo_folder
from cartograph.symbols import index_symbols


def already_indexed(repo_id: str) -> bool:
  """True if this repo already has chunks in the database."""
  try:
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
      row = conn.execute(
        "SELECT 1 FROM chunks WHERE repo_id = %s LIMIT 1",
        (repo_id,),
      ).fetchone()
    return row is not None
  except Exception:
    return False


def add_repo(url: str, force: bool = False) -> dict:
  """Paste a GitHub link → download it, index it, map it. Returns what was done."""
  repo_id = parse_github_url(url)

  if not force and already_indexed(repo_id):
    print(f"{repo_id} is already indexed. Skipping.")
    return {
      "repo_id": repo_id,
      "path": str(repo_folder(repo_id)),
      "cached": True,
    }

  repo_id, folder = clone_repo(url)                  # step 1: download
  print(f"Downloaded {repo_id} → {folder}")

  print("STEP 1: Starting chunk indexing...")
  chunks = index_repo(str(folder), repo_id)          # step 2: notes with sticker
  print(f"Indexed {chunks} chunks")

  print("STEP 2: Starting symbol indexing...")
  symbols = index_symbols(str(folder), repo_id)      # step 3: functions with sticker
  print(f"Indexed {symbols} symbols")

  print("STEP 3: Building summarized map...")
  build_summarized_map(str(folder), repo_id)         # step 4: its own map

  return {
    "repo_id": repo_id,
    "path": str(folder),
    "chunks": chunks,
    "symbols": symbols,
    "cached": False,
  }