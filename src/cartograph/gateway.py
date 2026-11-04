import os
from collections import defaultdict

from langchain_core.callbacks import BaseCallbackHandler
from langchain_groq import ChatGroq


from cartograph.llm import get_fallback_models, get_primary_model, groq_tool_model

EASY_JOBS = {"router", "judge", "summary"}

USAGE = defaultdict(int)


class UsageCounter(BaseCallbackHandler):
  """After every LLM call, add its tokens to this job's total."""

  def __init__(self, job: str):
    self.job = job

  def on_llm_end(self, response, **kwargs):
    for generation_list in response.generations:
      for generation in generation_list:
        message = getattr(generation, "message", None)
        usage = getattr(message, "usage_metadata", None) or {}
        USAGE[self.job] += usage.get("total_tokens", 0)

  def on_llm_error(self, error, **kwargs):
    print(f"MODEL ERROR {self.job}: {type(error).__name__}: {str(error)[:300]}")


def print_usage():
  total = sum(USAGE.values())
  print("\nUSAGE (tokens)")
  for job, tokens in sorted(USAGE.items(), key=lambda item: -item[1]):
    print(f"  {job:<10} {tokens:>8,}")
  print(f"  {'TOTAL':<10} {total:>8,}")


def pick_primary(job: str):
  """Small model for easy jobs, tool model for tool-calling jobs, main model for the rest."""
  if job in EASY_JOBS:
    return ChatGroq(model=os.getenv("GROQ_SMALL_MODEL", "openai/gpt-oss-20b"), temperature=0, timeout=20)
  if job == "agent":
    return groq_tool_model()
  return get_primary_model()


def get_model(
    job: str,
    form=None,
    tools=None,
    structured_method="function_calling",
):
    """Every part of Cartograph gets its model here."""
    primary = pick_primary(job)
    backups = get_fallback_models()

    if tools:
        primary = primary.bind_tools(tools)
        backups = [backup.bind_tools(tools) for backup in backups]

    if form:
        # The small gpt-oss model (router, judge, summary) is reliable with json_schema,
        # but garbles names with function_calling ('verdict' instead of 'Verdict').
        method = "json_schema" if job in EASY_JOBS else structured_method
        primary = primary.with_structured_output(form, method=method)
        backups = [backup.with_structured_output(form) for backup in backups]

    primary = primary.with_retry(stop_after_attempt=3)

    return primary.with_fallbacks(backups).with_config(
        callbacks=[UsageCounter(job)]
    )