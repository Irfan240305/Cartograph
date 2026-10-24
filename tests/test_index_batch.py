
import os
from dotenv import load_dotenv
import psycopg

from cartograph.indexer import code_files, chunk_file, create_table, embed_texts
from pathlib import Path
import numpy as np
from pgvector.psycopg import register_vector

load_dotenv(override=True)

repo = Path("data/repos/Irfan240305__OmniReserve").resolve()
repo_id = "omnireserve_batch_test"

files = code_files(str(repo))
if not files:
    raise RuntimeError(f"No indexable files found in {repo}")

chunks = []
for file in files:
    chunks.extend(chunk_file(file, repo))
    if len(chunks) >= 5:
        chunks = chunks[:5]
        break

if not chunks:
    raise RuntimeError("No chunks found")

print(f"Testing {len(chunks)} chunks from {repo}")

vectors = embed_texts([chunk["text"] for chunk in chunks])
print(f"Generated {len(vectors)} embeddings")

with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
    register_vector(conn)
    create_table(conn, len(vectors[0]))

    conn.execute("DELETE FROM chunks WHERE repo_id = %s", (repo_id,))

    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO chunks
                (repo_id, path, start_line, end_line, content, embedding)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            [
                (
                    repo_id,
                    chunk["path"],
                    chunk["start_line"],
                    chunk["end_line"],
                    chunk["text"],
                    np.array(vector),
                )
                for chunk, vector in zip(chunks, vectors)
            ],
        )

    count = conn.execute(
        "SELECT COUNT(*) FROM chunks WHERE repo_id = %s",
        (repo_id,),
    ).fetchone()[0]

print(f"SUCCESS: {count} test chunks saved in PostgreSQL")
