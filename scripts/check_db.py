import os

import psycopg
from dotenv import load_dotenv

load_dotenv(override=True)

with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
  version = conn.execute("SELECT version()").fetchone()[0]
  vector = conn.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'").fetchone()

print("Postgres:", version)
print("pgvector:", vector[0] if vector else "NOT enabled")