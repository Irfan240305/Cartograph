from cartograph.tools import keyword_rows, semantic_rows, rrf_merge

query = "how are secret files protected"

keyword = keyword_rows(query)
semantic = semantic_rows(query)
merged = rrf_merge(keyword, semantic)

def show(title, rows):
  print(f"\n{title}")
  for place, row in enumerate(rows[:5], start=1):
    print(f"  {place}. id {row[0]}  {row[1]} lines {row[2]}-{row[3]}")

show("KEYWORD (Judge 1)", keyword)
show("SEMANTIC (Judge 2)", semantic)
show("HYBRID (merged)", merged)