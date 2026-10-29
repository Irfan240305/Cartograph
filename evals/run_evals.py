import json
import time



from cartograph.graph import graph
from cartograph.tools import Context
from cartograph.gateway import print_usage

from langgraph.errors import GraphRecursionError

DATASET = "evals/dataset.json"
RESULTS = "evals/results.json"


def run_one(item: dict, number: int) -> dict:
  start = time.time()

  result = graph.invoke(
    {"messages": [{"role": "user", "content": item["question"]}]},
    context=Context(repo_path=".", repo_id="Irfan240305/Cartograph"),
    config={"configurable": {"thread_id": f"eval-{number}"}, "recursion_limit": 50},
  )

  seconds = round(time.time() - start, 1)
  answer = result.get("answer")

  return {
    "question": item["question"],
    "type": item["type"],
    "expected_files": item["expected_files"],
    "key_facts": item["key_facts"],
    "answer": answer.answer if answer else "",
    "sources": [s.path for s in answer.sources] if answer else [],
    "route": "blocked" if result.get("blocked") else result.get("kind"),
    "seconds": seconds,
  }


def main():
  questions = json.loads(open(DATASET, encoding="utf-8").read())
  results = []
  for number, item in enumerate(questions, start=1):
    print(f"[{number}/{len(questions)}] {item['question'][:70]}")
    try:
      record = run_one(item, number)
    except GraphRecursionError:
      record = {**item, "answer": "Could not determine - feature not found in codebase.", "sources": [], "route": None, "seconds": 0, "error": "recursion_limit"}
      print(f" ERROR: recursion limit reached")
    except Exception as e:
      record = {**item, "answer": "", "sources": [], "route": None, "seconds": 0, "error": str(e)}
      print(f"  ERROR: {e}")
    results.append(record)
    open(RESULTS, "w", encoding="utf-8").write(json.dumps(results, indent=2))
    time.sleep(30)  # avoid rate limits

  open(RESULTS, "w", encoding="utf-8").write(json.dumps(results, indent=2))
  print(f"\nSaved {len(results)} results to {RESULTS}")


if __name__ == "__main__":
  main()