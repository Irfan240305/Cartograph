from pathlib import Path

from cartograph.tools import is_secret, rrf_merge, safe_path

from cartograph.tools import is_eval_data

import pytest
pytestmark = pytest.mark.unit

def test_safe_path_allows_inside():
    assert safe_path(".", "src/cartograph/tools.py") is not None


def test_safe_path_blocks_escape():
    assert safe_path(".", "../../../etc/passwd") is None


def test_is_secret_blocks_env():
    assert is_secret(Path(".env")) is True


def test_is_secret_allows_env_example():
    assert is_secret(Path(".env.example")) is False


def test_is_secret_allows_normal_file():
    assert is_secret(Path("tools.py")) is False


def test_rrf_merge_combines_lists():
    list1 = [(1, "a"), (2, "b")]
    list2 = [(2, "b"), (3, "c")]
    merged = rrf_merge(list1, list2)
    ids = [row[0] for row in merged]
    assert 2 == ids[0]          # appears in both, ranks first
    assert len(merged) == 3     # no duplicates

def test_eval_answer_key_is_hidden():
    assert is_eval_data(Path("evals/dataset.json"))
    assert is_eval_data(Path("evals/results.json"))
    assert not is_eval_data(Path("evals/score.py"))
    assert not is_eval_data(Path("data/dataset.json"))

def test_code_files_includes_web_files_and_skips_lockfiles(tmp_path):
    from cartograph.indexer import code_files

    (tmp_path / "index.html").write_text("<h1>Hi</h1>")
    (tmp_path / "style.css").write_text("h1 { color: red; }")
    (tmp_path / "package-lock.json").write_text("{}")

    names = {file.name for file in code_files(str(tmp_path))}
    assert names == {"index.html", "style.css"}