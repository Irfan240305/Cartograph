import re  #checking the link
import shutil #Deleting the old copy of the repo if it exists
import subprocess #Running git clone from python
from pathlib import Path

import os
import stat

REPOS_DIR = Path("data/repos")
GITHUB_URL = re.compile(r"^https://github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?/?$")

def parse_github_url(url:str) -> str:
  match = GITHUB_URL.match(url.strip())
  if not match:
    raise ValueError("Only public https://github.com/owner/repo URLs are supported.")
  owner, name = match.groups()
  return f"{owner}/{name}"

def repo_folder(repo_id: str) -> Path:
  return REPOS_DIR / repo_id.replace("/", "__")

def force_remove(func, path, exc):
  """Windows fix: if a file is read-only, make it writable, then delete it."""
  os.chmod(path, stat.S_IWRITE)
  func(path)

def clone_repo(url: str) -> tuple[str, Path]:
  repo_id = parse_github_url(url)
  folder = repo_folder(repo_id)
  if folder.exists():
    shutil.rmtree(folder, onexc=force_remove)
  folder.parent.mkdir(parents=True, exist_ok=True)
  subprocess.run(
    ["git", "clone", "--depth", "1", f"https://github.com/{repo_id}.git", str(folder)],
    check=True, timeout=120,
  )
  return repo_id, folder

MAPS_DIR = Path("data/maps")


def map_file(repo_id: str) -> Path:
  """'psf/requests' -> data/maps/psf__requests.json"""
  return MAPS_DIR / f"{repo_id.replace('/', '__')}.json"