import os
from collections import defaultdict

from langchain_core.callbacks import BaseCallbackHandler
from langchain_groq import ChatGroq

from cartograph.llm import get_fallback_models, get_primary_model

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


def print_usage():
  total = sum(USAGE.values())
  print("\nUSAGE (tokens)")
  for job, tokens in sorted(USAGE.items(), key=lambda item: -item[1]):
    print(f"  {job:<10} {tokens:>8,}")
  print(f"  {'TOTAL':<10} {total:>8,}")


def pick_primary(job: str):
  """Small fast model for easy jobs, the main model for everything else."""
  if job in EASY_JOBS:
    return ChatGroq(model=os.getenv("GROQ_SMALL_MODEL", "openai/gpt-oss-20b"), temperature=0, timeout=20)
  return get_primary_model()


def get_model(job: str, form=None, tools=None):
  """Every part of Cartograph gets its model here. Retries and backups are always included."""
  primary = pick_primary(job)
  backups = get_fallback_models()

  if tools:
    primary = primary.bind_tools(tools)
    backups = [b.bind_tools(tools) for b in backups]

  if form:
    primary = primary.with_structured_output(form, method="function_calling")
    backups = [b.with_structured_output(form, method="function_calling") for b in backups]

  primary = primary.with_retry(stop_after_attempt=2)
  return primary.with_fallbacks(backups).with_config(callbacks=[UsageCounter(job)])