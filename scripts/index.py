from dotenv import load_dotenv

from cartograph.indexer import index_repo
from cartograph.symbols import index_symbols

from cartograph.repomap import build_summarized_map

load_dotenv(override=True)

REPO_ID = "Irfan240305/Cartograph"

print("Indexed chunks:", index_repo(".", REPO_ID))
print("Indexed symbols:", index_symbols(".", REPO_ID))
print("Built map:", bool(build_summarized_map(".", REPO_ID)))