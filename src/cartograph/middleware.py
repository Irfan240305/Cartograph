from langchain.agents.middleware import after_model, AgentState
from langgraph.runtime import Runtime

@after_model
def log_step(state: AgentState, runtime: Runtime) -> None:
  """Print which model ran, how many tokens it used, and what it decided."""
  message = state["messages" ][-1]

  if message.type != "ai":
    return None

  model = message.response_metadata.get("model_name", "unknown")
  tokens = (message.usage_metadata or {}).get("total_tokens", "?")

  if message.tool_calls:
    calls = ", ".join(f"{call['name']}({str(call['args'])[:80]})" for call in message.tool_calls)
    print(f"[step] {model} | tokens: {tokens} | tools: {calls}")
  else:
    print(f"[step] {model} | tokens: {tokens} | final answer")