import json

results = json.loads(open("evals/results.json", encoding="utf-8").read())

for i, r in enumerate(results):
    ef = r.get("expected_files", [])
    got = r.get("sources", [])
    if ef and got:
        expected = set(ef)
        actual = set(got)
        overlap = expected.intersection(actual)
        if len(overlap) < len(expected):
            print(f"[{i+1}] {r['question'][:60]}")
            print(f"  Expected: {ef}")
            print(f"  Got:      {got}")
            print(f"  Match:    {sorted(overlap) if overlap else 'NONE'}")
            print()