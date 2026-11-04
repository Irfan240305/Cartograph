import json

from cartograph.tools import keyword_rows, rrf_merge, semantic_rows

DATASET = "evals/dataset.json"
REPO_ID = "Irfan240305/Cartograph"


def ranked_files(rows):
    """Turn a ranked list of chunks into a ranked list of files (no duplicates)."""
    files = []
    for _id, path, *_rest in rows:
        if path not in files:
            files.append(path)
    return files


def first_rank(files, expected):
    """Position (1, 2, 3...) of the first correct file, or None if not found."""
    for position, path in enumerate(files, start=1):
        if path in expected:
            return position
    return None

def file_recall(rows, expected, k):
    """Share of the expected files that appear in the top-k CHUNKS (what the agent actually sees)."""
    seen = {path for _id, path, *_rest in rows[:k]}
    return len(seen & expected) / len(expected)

def search(method, question):
    """Run one search method, exactly like the agent's tools do."""
    if method == "keyword":
        return keyword_rows(question, REPO_ID, 20)
    if method == "semantic":
        return semantic_rows(question, REPO_ID, 20)
    return rrf_merge(keyword_rows(question, REPO_ID, 20), semantic_rows(question, REPO_ID, 20))


def evaluate(method, items):
    recall5 = recall10 = reciprocal_ranks = 0.0
    for item in items:
        rows = search(method, item["question"])
        expected = set(item["expected_files"])
        recall5 += file_recall(rows, expected, 5)
        recall10 += file_recall(rows, expected, 10)
        rank = first_rank(ranked_files(rows), expected)
        if rank:
            reciprocal_ranks += 1 / rank
    n = len(items)
    return recall5 / n, recall10 / n, reciprocal_ranks / n


def main():
    items = [item for item in json.load(open(DATASET, encoding="utf-8")) if item.get("expected_files")]

    groups = {"all": items}
    for item in items:
        groups.setdefault(item["type"], []).append(item)

    for name, group in groups.items():
        print(f"\n=== {name} ({len(group)} questions) ===")
        print(f"{'method':<10} {'Recall@5':>9} {'Recall@10':>10} {'MRR':>6}")
        for method in ("keyword", "semantic", "hybrid"):
            recall5, recall10, mrr = evaluate(method, group)
            print(f"{method:<10} {recall5:>9.1%} {recall10:>10.1%} {mrr:>6.2f}")

if __name__ == "__main__":
    main()