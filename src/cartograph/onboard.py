from cartograph.indexer import index_repo
from cartograph.repomap import build_summarized_map
from cartograph.repos import clone_repo
from cartograph.symbols import index_symbols


def add_repo(url: str) -> dict:
  """Paste a GitHub link → download it, index it, map it. Returns what was done."""
  repo_id, folder = clone_repo(url)                  # step 1: download
  print(f"Downloaded {repo_id} → {folder}")

  chunks = index_repo(str(folder), repo_id)          # step 2: notes with sticker
  print(f"Indexed {chunks} chunks")

  symbols = index_symbols(str(folder), repo_id)      # step 3: functions with sticker
  print(f"Indexed {symbols} symbols")

  build_summarized_map(str(folder), repo_id)         # step 4: its own map

  return {"repo_id": repo_id, "path": str(folder), "chunks": chunks, "symbols": symbols}