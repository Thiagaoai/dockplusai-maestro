#!/usr/bin/env python3
"""
Session memory CLI — save and retrieve MAESTRO dev session logs from Supabase.

Usage:
  python scripts/session_memory.py last              # show last session (onde paramos?)
  python scripts/session_memory.py save "title"      # save a new session entry
  python scripts/session_memory.py list              # list last 10 sessions
"""
import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

# Load .env
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

try:
    from supabase import create_client
except ImportError:
    print("Run: uv sync  (supabase-py not installed)")
    sys.exit(1)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def cmd_last():
    res = (
        client.table("session_memory")
        .select("*")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if not res.data:
        print("Nenhuma sessão salva ainda.")
        return
    row = res.data[0]
    print(f"\n{'='*60}")
    print(f"ÚLTIMA SESSÃO — {row['session_date']} ({row['created_at'][:19]})")
    print(f"{'='*60}")
    print(f"TÍTULO: {row['title']}")
    print(f"\nRESUMO:\n{row['summary']}")
    pending = row.get("pending") or []
    done = row.get("done") or []
    if done:
        print(f"\n✅ FEITO:")
        for item in done:
            print(f"  • {item}")
    if pending:
        print(f"\n⏳ PENDENTE:")
        for item in pending:
            print(f"  • {item}")
    meta = row.get("metadata") or {}
    if meta:
        print(f"\nMETADATA: {json.dumps(meta, indent=2)}")
    print(f"{'='*60}\n")


def cmd_list():
    res = (
        client.table("session_memory")
        .select("id, session_date, title, created_at")
        .order("created_at", desc=True)
        .limit(10)
        .execute()
    )
    if not res.data:
        print("Nenhuma sessão salva.")
        return
    print(f"\n{'='*60}")
    print("ÚLTIMAS SESSÕES")
    print(f"{'='*60}")
    for row in res.data:
        print(f"[{row['session_date']}] {row['title']}")
    print(f"{'='*60}\n")


def cmd_save(title: str, summary: str | None, pending: list, done: list, metadata: dict):
    data = {
        "session_date": date.today().isoformat(),
        "title": title,
        "summary": summary or title,
        "pending": pending,
        "done": done,
        "metadata": metadata,
    }
    res = client.table("session_memory").insert(data).execute()
    if res.data:
        print(f"✅ Sessão salva: {res.data[0]['id']}")
    else:
        print("Erro ao salvar sessão.")


def main():
    parser = argparse.ArgumentParser(description="MAESTRO session memory")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("last", help="Show last session")
    sub.add_parser("list", help="List last 10 sessions")

    save_p = sub.add_parser("save", help="Save a session entry")
    save_p.add_argument("title", help="Session title")
    save_p.add_argument("--summary", default=None, help="Full summary text")
    save_p.add_argument("--pending", default="[]", help="JSON array of pending items")
    save_p.add_argument("--done", default="[]", help="JSON array of completed items")
    save_p.add_argument("--meta", default="{}", help="JSON metadata")

    args = parser.parse_args()

    if args.cmd == "last":
        cmd_last()
    elif args.cmd == "list":
        cmd_list()
    elif args.cmd == "save":
        cmd_save(
            args.title,
            args.summary,
            json.loads(args.pending),
            json.loads(args.done),
            json.loads(args.meta),
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
