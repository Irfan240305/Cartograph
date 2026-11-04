from cartograph.answers import parse_answer


def test_answer_and_sources_are_split():
    text = (
        "safe_path is in tools.py.\n\n"
        "SOURCES:\n"
        "- src/cartograph/tools.py: defines safe_path\n"
        "- `src/cartograph/guards.py`: make_safe"
    )
    answer = parse_answer(text)
    assert answer.answer == "safe_path is in tools.py."
    assert [s.path for s in answer.sources] == ["src/cartograph/tools.py", "src/cartograph/guards.py"]


def test_no_sources_section():
    answer = parse_answer("Just an answer.")
    assert answer.answer == "Just an answer."
    assert answer.sources == []


def test_markdown_sources_heading():
    answer = parse_answer("Answer.\n**Sources:**\n- a.py: x")
    assert answer.sources[0].path == "a.py"