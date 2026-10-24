from pathlib import Path

from cartograph.tools import is_secret, rrf_merge, safe_path


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