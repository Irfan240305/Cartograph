
import os
import tempfile
from pathlib import Path

import psycopg

from cartograph.symbols import index_symbols

TEST_REPO_ID = "tree-sitter-integration-test"


def main():
    if not os.environ.get("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is not configured.")

    with tempfile.TemporaryDirectory() as temp_dir:
        repo = Path(temp_dir)

        samples = {
            "sample.py": "def py_hello():\n    pass\n\nclass PyGreeter:\n    pass\n",
            "Sample.java": "class JavaGreeter { void java_hello() {} }",
            "sample.js": "function js_hello() {}\nclass JsGreeter {}",
            "sample.ts": "function ts_hello(): void {}\nclass TsGreeter {}",
        }

        for filename, content in samples.items():
            (repo / filename).write_text(content, encoding="utf-8")

        try:
            count = index_symbols(str(repo), TEST_REPO_ID)

            with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
                rows = conn.execute(
                    """
                    SELECT name, kind, path
                    FROM symbols
                    WHERE repo_id = %s
                    ORDER BY path, line
                    """,
                    (TEST_REPO_ID,),
                ).fetchall()

            print("Symbols returned by indexer:", count)
            print("Symbols saved in database:", len(rows))
            for row in rows:
                print(row)

            expected = {
                "py_hello", "PyGreeter",
                "java_hello", "JavaGreeter",
                "js_hello", "JsGreeter",
                "ts_hello", "TsGreeter",
            }
            actual = {row[0] for row in rows}

            missing = expected - actual
            if missing:
                raise AssertionError(f"Missing symbols: {sorted(missing)}")

            print("PASS: All expected symbols were saved.")

        finally:
            # Remove only the test records, never your real repository data.
            with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
                conn.execute(
                    "DELETE FROM symbols WHERE repo_id = %s",
                    (TEST_REPO_ID,),
                )


if __name__ == "__main__":
    main()
