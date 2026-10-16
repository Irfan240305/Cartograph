from cartograph.graph import graph
from cartograph.tools import Context

config = {"configurable": {"thread_id": "memory-test"}}                                        # chat number

before = len(graph.get_state(config).values.get("messages", []))                               # count messages in this chat
graph.invoke(
  {"messages": [{"role": "user", "content": ""}]},                                               # an empty question
  context=Context(repo_path=".", repo_id="Irfan240305/Cartograph"),
  config=config,
)
after = len(graph.get_state(config).values.get("messages", []))                                # count again
print(f"Messages in this conversation: before={before}, after={after}")