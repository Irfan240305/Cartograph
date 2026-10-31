from langchain_protocol import Command

from cartograph.graph import graph
from cartograph.tools import Context

config = {"configurable": {"thread_id": "session-1"}, "recursion_limit": 20}
context = Context(repo_path=".", repo_id="Irfan240305/Cartograph")


def run(inputs):
  for chunk in graph.stream(inputs, context=context, config=config,  stream_mode="updates"):
    if "agent" in chunk:
      reply = chunk["agent"]["messages"][-1]
      if reply.tool_calls:
        for call in reply.tool_calls:
          print(f" ... {call['name']}({call['args']})")
      else:
        print(f" ... done exploring code, writing the answer")




def ask(question):
  print("Q: " + question)
  run({"messages":[{"role":"user","content":question}]})

  state = graph.get_state(config)
  while state.next:
    cartograph_question = state.tasks[0].interrupts[0].value["question"]
    user_reply = input(f"\nCartograph asks: {cartograph_question}\nYou: ")
    run(Command(resume={"data": user_reply}))
    state = graph.get_state(config)

  answer = state.values["answer"]
  print("\nA:", answer.answer)
  for source in answer.sources:
    print("  -", source.path)
  print()



ask("Where is the read_file tool defined?")
ask("Explain how this whole project is organised.")

ask("How does Cartograph check its answers before finishing?")
ask("How does a question travel through Cartograph, from start to answer?")