import json
from pathlib import Path

from cartograph.indexer import CODE_EXTENSIONS

from cartograph.repos import map_file
from cartograph.tools import IGNORED_DIRS, is_secret

from cartograph.gateway import get_model

def file_node(file: Path, repo: Path) -> dict:
  return {
    "name": file.name,
    "path": file.relative_to(repo).as_posix(),
    "type": "file",
  }


def folder_node(folder: Path, repo: Path) -> dict | None:
  children = []
  for item in sorted(folder.iterdir()):
    if item.is_dir():
      if item.name in IGNORED_DIRS:
        continue
      child = folder_node(item, repo)
      if child:
        children.append(child)
    elif item.suffix in CODE_EXTENSIONS and not is_secret(item):
      children.append(file_node(item, repo))

  if not children:
    return None

  return {
    "name": folder.name,
    "path": folder.relative_to(repo).as_posix(),
    "type": "folder",
    "children": children,
  }


def build_repo_tree(repo_path: str) -> dict:
  """Build the folder/file tree only. Saving happens in build_summarized_map."""
  repo = Path(repo_path).resolve()
  return folder_node(repo, repo)


def summarize_file(file: Path, repo: Path) -> str:
  code = file.read_text(encoding="utf-8", errors="ignore")[:3000]
  prompt = (
    "Summarize what this file does in ONE short sentence (max 20 words). "
    "Mention its key functions or purpose.\n\n"
    f"File: {file.relative_to(repo).as_posix()}\n\n{code}"
  )
  return get_model("summary").invoke(prompt).content.strip()


def summarize_folder(node: dict) -> str:
  lines = [f"- {child['name']}: {child.get('summary', '')}" for child in node["children"]]
  prompt = (
    "Summarize what this folder contains in ONE short sentence (max 20 words), "
    "based on these summaries of its contents.\n\n"
    f"Folder: {node['path']}\n" + "\n".join(lines)
  )
  return get_model("summary").invoke(prompt).content.strip()


def add_summaries(node: dict, repo: Path) -> None:
  if node["type"] == "file":
    print(f"Summarizing file: {node['path']}")
    node["summary"] = summarize_file(repo / node["path"], repo)
    return
  for child in node["children"]:
    add_summaries(child, repo)
  node["summary"] = summarize_folder(node)


def build_summarized_map(repo_path: str, repo_id: str) -> dict:
  """Build the tree, add a summary to every file and folder, and save it under the project's name."""
  repo = Path(repo_path).resolve()
  tree = build_repo_tree(repo_path)
  print("Summarizing files and folders...")
  add_summaries(tree, repo)

  path = map_file(repo_id)
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(json.dumps(tree, indent=2), encoding="utf-8")
  print(f"Saved summarized map to {path}")
  return tree