from cartograph.tools import keyword_search

result = keyword_search.invoke({"query": "secret env file"})
for i, block in enumerate(result.split("\n\n---\n\n"), start=1):
  print(i, block.splitlines()[0])