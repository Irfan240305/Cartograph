import cartograph.graph as graph_module

import pytest
pytestmark = pytest.mark.unit

def test_keeps_going_under_the_limit():
    assert graph_module.after_tools({"steps": 3}) == "agent"


def test_stops_at_the_limit():
    assert graph_module.after_tools({"steps": graph_module.MAX_STEPS}) == "respond"


def test_new_question_with_no_counter_keeps_going():
    assert graph_module.after_tools({}) == "agent"