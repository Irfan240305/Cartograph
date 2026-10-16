from cartograph.indexer import index_repo
from cartograph.symbols import index_symbols

count = index_repo(".")
print("Indexed chunks:", count)
print("Indexed symbols:", index_symbols("."))