import os
from pathlib import Path

import psycopg
import pytest
from dotenv import load_dotenv

from cartograph.indexer import index_repo
from cartograph.symbols import index_symbols
from cartograph.tools import keyword_rows, rrf_merge, semantic_rows

pytestmark = pytest.mark.integration
load_dotenv(override=True)

REPO_ID = "test/tiny_repo"
FIXTURE = Path(__file__).parent / "fixtures" / "tiny_repo"


@pytest.fixture(scope="module")
def indexed():
    if not os.getenv("DATABASE_URL"):
        pytest.skip("needs PostgreSQL")
    index_symbols(str(FIXTURE), REPO_ID)
    index_repo(str(FIXTURE), REPO_ID)
    yield
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        conn.execute("DELETE FROM chunks WHERE repo_id = %s", (REPO_ID,))
        conn.execute("DELETE FROM symbols WHERE repo_id = %s", (REPO_ID,))


def test_keyword_search_finds_the_right_file(indexed):
    paths = [row[1] for row in keyword_rows("convert celsius fahrenheit temperature", REPO_ID)]
    assert paths and paths[0] == "convert.py"


def test_hybrid_search_finds_the_right_file(indexed):
    question = "how are two numbers added together"
    merged = rrf_merge(keyword_rows(question, REPO_ID), semantic_rows(question, REPO_ID))
    assert "calc.py" in [row[1] for row in merged[:3]]


def test_symbols_are_indexed(indexed):
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        rows = conn.execute(
            "SELECT name, path FROM symbols WHERE repo_id = %s ORDER BY name",
            (REPO_ID,),
        ).fetchall()
    assert ("TemperatureConverter", "convert.py") in rows
    assert ("add_numbers", "calc.py") in rows