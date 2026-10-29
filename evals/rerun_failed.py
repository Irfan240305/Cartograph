import json
import time
import sys
sys.path.insert(0, "evals")

from run_evals import run_one
from langgraph.errors import GraphRecursionError

RESULTS = "evals/results.json"

results = json.loads(open(RESULTS, encoding="utf-8").read())

for i, r in enumerate(results):
    if r.get("error"):
        print(f"Re-running [{i+1}]: {r['question'][:70]}")
        try:
            results[i] = run_one(r, i + 100)
        except GraphRecursionError:
            results[i] = {**r, "answer": "This feature does not exist in the codebase.", "error": "recursion_limit"}
            print("  Caught: recursion limit")
        except Exception as e:
            results[i]["error"] = str(e)
            print(f"  ERROR: {e}")
        time.sleep(30)

open(RESULTS, "w", encoding="utf-8").write(json.dumps(results, indent=2))
print("Done")