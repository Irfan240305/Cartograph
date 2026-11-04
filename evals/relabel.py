import json
import sys

source, target = sys.argv[1], sys.argv[2]

dataset = {
    item["question"]: item
    for item in json.load(open("evals/dataset.json", encoding="utf-8"))
}
results = json.load(open(source, encoding="utf-8"))

updated = []
for record in results:
    item = dataset.get(record["question"])
    if item is None:
        print(f"Dropped (question replaced in dataset): {record['question'][:60]}")
        continue
    record["expected_files"] = item["expected_files"]
    record["key_facts"] = item["key_facts"]
    record["type"] = item["type"]
    updated.append(record)

json.dump(updated, open(target, "w", encoding="utf-8"), indent=2)
print(f"Saved {len(updated)} results to {target}")