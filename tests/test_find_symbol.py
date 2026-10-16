from types import SimpleNamespace

from cartograph.tools import Context, find_symbol

mine = SimpleNamespace(context=Context(repo_path=".", repo_id="Irfan240305/Cartograph"))
other = SimpleNamespace(context=Context(repo_path=".", repo_id="psf/requests"))

print(find_symbol.func("safe_path", mine))
print("---")
print(find_symbol.func("secret", mine))
print("---")
print(find_symbol.func("banana", mine))
print("--- other repo's sticker ---")
print(find_symbol.func("safe_path", other))