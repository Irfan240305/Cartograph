from cartograph.tools import semantic_search

result = semantic_search.invoke({"query": "how are secret files protected"})

for i, block in enumerate(result.split("\n\n---\n\n"), start=1):
  print(i, block.splitlines()[0])