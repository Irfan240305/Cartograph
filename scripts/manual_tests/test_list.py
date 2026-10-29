from types import SimpleNamespace

from cartograph.tools import Context, list_files

runtime = SimpleNamespace(context=Context(repo_path="."))

print("=== 1. Top level ===")
print(list_files.func(runtime))

print("\n=== 2. A sub-folder ===")
print(list_files.func(runtime, "src"))

print("\n=== 3. Not a folder ===")
print(list_files.func(runtime, "README.md"))

print("\n=== 4. Escape attempt ===")
print(list_files.func(runtime, "../.."))