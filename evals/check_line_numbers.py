import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

load_dotenv(override=True)

REPO_ID = "Irfan240305/Cartograph"
ROOT = Path("data/repos/Irfan240305__Cartograph")

with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
    rows = conn.execute(
        "SELECT path, start_line, end_line, content FROM chunks WHERE repo_id = %s",
        (REPO_ID,),
    ).fetchall()

correct = 0
for path, start, end, content in rows:
    lines = (ROOT / path).read_text(encoding="utf-8", errors="ignore").splitlines()
    snippet = "\n".join(lines[start - 1:end])
    if content.strip() and content.strip() in snippet:
        correct += 1
    else:
        print(f"MISMATCH {path} lines {start}-{end}")

print(f"\nLine numbers correct: {correct}/{len(rows)} = {correct / len(rows):.1%}")