"""Apply SQL files in migrations/ in filename order. Idempotent (IF NOT EXISTS everywhere)."""
import pathlib
import sys

import psycopg2

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from app.config import settings

MIGRATIONS_DIR = pathlib.Path(__file__).resolve().parent.parent / "migrations"


def main() -> None:
    conn = psycopg2.connect(settings.database_url)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
                print(f"Applying {path.name}...")
                cur.execute(path.read_text())
        print("Done.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
