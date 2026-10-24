from types import SimpleNamespace

from cartograph.tools import Context, semantic_search

runtime = SimpleNamespace(context=Context(repo_path=".", repo_id="Irfan240305/Cartograph"))

print(semantic_search.func("how are secret files protected", runtime))