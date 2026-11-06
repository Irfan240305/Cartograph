from langchain_core.messages import AIMessage

import cartograph.graph as graph_module
from langchain_core.messages import HumanMessage, SystemMessage

import pytest
pytestmark = pytest.mark.unit

class FakeModel:
    def invoke(self, messages):
        self.received = messages        # remember what we were given
        return AIMessage(content="ok")  # pretend to answer

def test_agent_sends_system_prompt(monkeypatch):
    fake = FakeModel()
    monkeypatch.setattr(graph_module, "model", fake)   # swap real AI for the fake

    state = {"messages": [HumanMessage("Where is safe_path defined?")]}
    graph_module.agent(state, None)

    first = fake.received[0]
    assert isinstance(first, SystemMessage)                    # is message 0 a system message?
    assert first.content == graph_module.SYSTEM_PROMPT  # does it contain your rules?
    assert fake.received[1].content == "Where is safe_path defined?"  # question comes second