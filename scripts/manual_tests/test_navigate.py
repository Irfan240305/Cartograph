from types import SimpleNamespace

from cartograph.tools import Context, navigate_repo

fake_runtime = SimpleNamespace(context=Context(repo_path="."))
print(navigate_repo.func(fake_runtime))