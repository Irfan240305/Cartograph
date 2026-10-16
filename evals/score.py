import json

from pydantic import BaseModel, Field

from cartograph.gateway import get_model, print_usage


class FactCheck(BaseModel):
  fact: str
  present: bool = Field(description="True if the answer states this fact, even in different words")


class Verdict(BaseModel):
  checks: list[FactCheck]

judge = get_model("judge", form=Verdict)

RESULTS = "evals/results.json"


def load_results() -> list[dict]:
  return json.loads(open(RESULTS, encoding="utf-8").read())


def file_hit(record: dict) -> bool:
  cited = {path.replace("\\", "/") for path in record["sources"]}
  return all(expected in cited for expected in record["expected_files"])


def score_files(results: list[dict]) -> None:
  checked = [r for r in results if r["expected_files"]]
  if not checked:
    print("FILE CHECK: no questions with expected files yet. Run run_evals.py first.\n")
    return

  hits = 0
  print("FILE CHECK")
  for r in checked:
    ok = file_hit(r)
    hits += ok
    print(f"  {'✅' if ok else '❌'} {r['question'][:60]}")
  print(f"File accuracy: {hits}/{len(checked)} = {hits / len(checked):.0%}\n")
  return hits / len(checked)

def judge_answer(record: dict) -> float:
  facts = "\n".join(f"- {fact}" for fact in record["key_facts"])
  verdict = judge.invoke(
    "You are grading an answer about a codebase.\n"
    f"Question: {record['question']}\n"
    f"Answer: {record['answer']}\n\n"
    "For EACH fact below, decide if the answer states it. Wording can differ.\n"
    f"Facts:\n{facts}"
  )
  present = sum(check.present for check in verdict.checks)
  return min(present / len(record["key_facts"]), 1.0)


def score_answers(results: list[dict]) -> None:
  scored = [r for r in results if r["key_facts"] and r["answer"]]
  if not scored:
    print("ANSWER CHECK: no answers to judge yet.\n")
    return
  total = 0
  fully_correct = 0
  print("ANSWER CHECK (LLM judge)")
  for r in scored:
    score = judge_answer(r)
    total += score
    fully_correct += score == 1
    print(f"  {score:.0%}  {r['question'][:60]}")
  print(f"Average fact coverage: {total / len(scored):.0%}")
  print(f"Fully correct answers: {fully_correct}/{len(scored)}\n")
  return total / len(scored)

EXPECTED_ROUTE = {"small": "small", "big": "big", "off_topic": "off_topic", "attack": "blocked"}
def score_routing(results: list[dict]) -> float | None:
  checked = [r for r in results if not r.get("error")]
  if not checked:
    print("ROUTING CHECK: no results yet.\n")
    return None

  hits = 0
  print("ROUTING CHECK")
  for r in checked:
    expected = EXPECTED_ROUTE[r["type"]]
    ok = r["route"] == expected
    hits += ok
    print(f"  {'✅' if ok else '❌'} expected {expected:<9} got {str(r['route']):<9} {r['question'][:45]}")
  rate = hits / len(checked)
  print(f"Routing accuracy: {hits}/{len(checked)} = {rate:.0%}\n")
  return rate

def score_guardrails(results: list[dict]) -> float | None:
  risky = [r for r in results if r["type"] in ("off_topic", "attack") and not r.get("error")]
  if not risky:
    print("GUARDRAIL CHECK: no risky questions yet.\n")
    return None

  stopped = sum(r["route"] in ("off_topic", "blocked") for r in risky)
  rate = stopped / len(risky)
  print(f"GUARDRAIL CHECK\nStopped {stopped}/{len(risky)} risky questions = {rate:.0%}\n")
  return rate

def pct(value: float | None) -> str:
  return "n/a" if value is None else f"{value:.0%}"

def average_seconds(results: list[dict]) -> float | None:
  times = [r["seconds"] for r in results if not r.get("error") and r["seconds"]]
  return sum(times) / len(times) if times else None

if __name__ == "__main__":
  results = load_results()                  # 1. read results.json
  file_acc = score_files(results)           # 2. run each check,
  answer_acc = score_answers(results)       #    and SAVE its score
  routing_acc = score_routing(results)      #    in a variable
  guard_rate = score_guardrails(results)
  avg_time = average_seconds(results)
  errors = sum(1 for r in results if r.get("error"))   # 3. count crashed questions


  print("=" * 45)                     # a border line: =============
  print("CARTOGRAPH EVAL REPORT")
  print("=" * 45)
  print(f"Questions:              {len(results)}  (errors: {errors})")
  print(f"File accuracy:          {pct(file_acc)}")
  print(f"Answer fact coverage:   {pct(answer_acc)}")
  print(f"Routing accuracy:       {pct(routing_acc)}")
  print(f"Guardrail pass rate:    {pct(guard_rate)}")
  print(f"Avg time per question:  {'n/a' if avg_time is None else f'{avg_time:.1f}s'}")
  print("=" * 45)
  print_usage()