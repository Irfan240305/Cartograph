from cartograph.tools import safe_path

print(safe_path(".", "README.md"))
print(safe_path(".", "src/cartograph/llm.py"))
print(safe_path(".", "../../Windows"))