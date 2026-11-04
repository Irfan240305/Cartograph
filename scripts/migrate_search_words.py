import os

import psycopg
from dotenv import load_dotenv

load_dotenv(override=True)

with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
    conn.execute("ALTER TABLE chunks DROP COLUMN IF EXISTS search_words")
    conn.execute("""
        ALTER TABLE chunks ADD COLUMN search_words TSVECTOR GENERATED ALWAYS AS (
          to_tsvector('english', content || ' ' || regexp_replace(content, '([a-z0-9])([A-Z])', '\\1 \\2', 'g'))
        ) STORED
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS chunks_words ON chunks USING GIN (search_words)")
print("search_words rebuilt with camelCase splitting")