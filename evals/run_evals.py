import json
import os
import subprocess
import time
import uuid
from datetime import datetime
from pathlib import Path
import sys

from langgraph.errors import GraphRecursionError

from cartograph.graph import graph
from cartograph.tools import Context

DATASET = sys.argv[1] if len(sys.argv) > 1 else "evals/dataset.json"
RESULTS = sys.argv[2] if len(sys.argv) > 2 else "evals/results.json"

RUN_ID = uuid.uuid4().hex[:8]


def is_rate_limit_error(error: Exception) -> bool:
  message = str(error).lower()
  return any(marker in message for marker in (
    "rate limit",
    "rate_limit",
    "too many requests",
    "resource_exhausted",
    "quota exceeded",
    "429",
  ))


def run_with_retry(item: dict, number: int) -> dict:
  try:
    return run_one(item, number)
  except GraphRecursionError:
    raise
  except Exception as error:
    if not is_rate_limit_error(error):
      raise
    print("  Rate limit encountered; waiting 60 seconds before retry")
    time.sleep(60)
    return run_one(item, number)


def run_one(item: dict, number: int) -> dict:
  start = time.time()

  result = graph.invoke(
    {"messages": [{"role": "user", "content": item["question"]}]},
    context=Context(repo_path="data/repos/Irfan240305__Cartograph", repo_id="Irfan240305/Cartograph"),
    config={"configurable": {"thread_id": f"eval-{RUN_ID}-{number}"}, "recursion_limit": 50},
  )

  seconds = round(time.time() - start, 1)
  answer = result.get("answer")

  record = {
    "question": item["question"],
    "type": item["type"],
    "expected_files": item["expected_files"],
    "key_facts": item["key_facts"],
    "answer": answer.answer if answer else "",
    "sources": [s.path for s in answer.sources] if answer else [],
    "route": "blocked" if result.get("blocked") else result.get("kind"),
    "seconds": seconds,
  }

  if result.get("failed"):
    record["error"] = "failed: " + record["answer"]

  return record


def save_run(results: list[dict]) -> Path:
  """Keep a copy of this run with the settings that produced it."""
  folder = Path("evals/runs") / f"{datetime.now():%Y-%m-%d_%H%M}_{RUN_ID}"
  folder.mkdir(parents=True, exist_ok=True)
  commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
  config = {
    "commit": commit,
    "dataset": DATASET,
    "questions": len(results),
    "groq_model": os.getenv("GROQ_MODEL"),
    "groq_tool_model": os.getenv("GROQ_TOOL_MODEL", "openai/gpt-oss-120b"),
    "groq_small_model": os.getenv("GROQ_SMALL_MODEL"),
    "embedding_model": os.getenv("EMBEDDING_MODEL"),
  }
  (folder / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
  (folder / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
  return folder


def main():
  questions = json.loads(open(DATASET, encoding="utf-8").read())
  results = []
  for number, item in enumerate(questions, start=1):
    print(f"[{number}/{len(questions)}] {item['question'][:70]}")
    try:
      record = run_with_retry(item, number)
    except GraphRecursionError:
      record = {**item, "answer": "", "sources": [], "route": None, "seconds": 0, "error": "recursion_limit"}
      print(" ERROR: recursion limit reached")
    except Exception as e:
      record = {**item, "answer": "", "sources": [], "route": None, "seconds": 0, "error": str(e)}
      print(f"  ERROR: {e}")
    results.append(record)
    open(RESULTS, "w", encoding="utf-8").write(json.dumps(results, indent=2))
    time.sleep(30)  # avoid rate limits

  open(RESULTS, "w", encoding="utf-8").write(json.dumps(results, indent=2))
  print(f"\nSaved {len(results)} results to {RESULTS}")
  print(f"Run archived in {save_run(results)}")


if __name__ == "__main__":
  main()