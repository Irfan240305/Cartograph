from cartograph.repomap import build_summarized_map

tree = build_summarized_map(".")
print("\nProject:", tree["summary"])
