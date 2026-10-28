"""Apply one SQL migration file to a Supabase Postgres database named by an env var (never printed).

    .venv/bin/python scripts/apply_migration.py --env SUPABASE_TEST_DB_URL supabase_migrations/<file>.sql

Statements are split on ';' (the migrations here have no functions or quoted semicolons).
TLS is verified with certs/supabase-prod-ca-2021.crt.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import agents  # noqa: E402,F401  (loads .env)
from agents.publication import _Postgres  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", required=True, help="env var holding the postgresql:// URL, e.g. SUPABASE_TEST_DB_URL")
    ap.add_argument("sql_file")
    args = ap.parse_args()
    url = os.getenv(args.env)
    if not url or not url.startswith(("postgresql://", "postgres://")):
        sys.exit(f"{args.env} 未設定或不是 postgresql:// 連線字串")
    db = _Postgres(url)
    text = (ROOT / args.sql_file).read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines() if not ln.strip().startswith("--")]
    statements = [s.strip() for s in "\n".join(lines).split(";") if s.strip()]
    for s in statements:
        db.run(s)
        print("ok:", " ".join(s.split())[:90])
    print(f"applied {len(statements)} statements from {args.sql_file} to {args.env}")


if __name__ == "__main__":
    main()
