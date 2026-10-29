import os

import psycopg

from cartograph.indexer import index_repo
from cartograph.repomap import build_summarized_map
from cartograph.repos import clone_repo, parse_github_url, repo_folder
from cartograph.symbols import index_symbols

from pathlib import Path

import logging
logger = logging.getLogger(__name__)

MAX_REPO_FILES = 5000
# MAX_FILE_SIZE_BYTES = 1 * 1024 * 1024  # 1 MB
IGNORED_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
    "target",
    "data",
}


def count_repo_files(folder: str | Path) -> int:
    """Count eligible files while ignoring generated and dependency directories."""
    root = Path(folder)
    count = 0

    for current_root, dirs, files in os.walk(root):
        # Don't descend into dependency, generated, or Git directories.
        dirs[:] = [
            name for name in dirs
            if name not in IGNORED_DIRS
        ]

        count += len(files)

        if count > MAX_REPO_FILES:
            return count

    return count

# def is_file_too_large(file_path: str | Path) -> bool:
#     """Return True if a file exceeds the maximum allowed size."""
#     try:
#         return Path(file_path).stat().st_size > MAX_FILE_SIZE_BYTES
#     except OSError:
#         return True


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
    logger.info("%s is already indexed. Skipping.", repo_id)
    
    return {
      "repo_id": repo_id,
      "path": str(repo_folder(repo_id)),
      "cached": True,
    }

  repo_id, folder = clone_repo(url)                  # step 1: download
  logger.info("Downloaded %s to %s", repo_id, folder)

  file_count = count_repo_files(folder)
  logger.info("Repository contains %d files", file_count)

  if file_count > MAX_REPO_FILES:
    raise ValueError(
       f"Repository exceeds the maximum allowed count "
       f"({MAX_REPO_FILES} files). Found more than "
       f"{MAX_REPO_FILES} eligible files."
    )

  logger.info("STEP 1: Starting chunk indexing...")
  chunks = index_repo(str(folder), repo_id)          # step 2: notes with sticker
  logger.info("Indexed %d chunks", chunks)

  logger.info("STEP 2: Starting symbol indexing...")
  symbols = index_symbols(str(folder), repo_id)      # step 3: functions with sticker
  logger.info("Indexed %d symbols", symbols)

  logger.info("STEP 3: Building summarized map...")
  try:
    build_summarized_map(str(folder), repo_id)         # step 4: its own map
  except Exception :
        logger.exception("Map generation failed; continuing without the summarized map")

  return {
    "repo_id": repo_id,
    "path": str(folder),
    "chunks": chunks,
    "symbols": symbols,
    "cached": False,
  }