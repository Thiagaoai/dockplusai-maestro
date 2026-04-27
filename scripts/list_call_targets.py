#!/usr/bin/env python3
"""List Roberts prospecting contacts to call after Resend delivery events."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from maestro.config import get_settings
from maestro.repositories.supabase_store import SupabaseStore
from maestro.services.call_targets import load_call_targets


def main() -> None:
    parser = argparse.ArgumentParser(description="List prospecting contacts ready for phone follow-up.")
    parser.add_argument("--business", default="roberts")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--json", action="store_true", help="Print JSON instead of a table.")
    args = parser.parse_args()

    settings = get_settings()
    store = SupabaseStore(settings)
    targets = asyncio.run(
        load_call_targets(store, business=args.business, days=args.days, limit=args.limit)
    )

    if args.json:
        print(
            json.dumps(
                [
                    {
                        "name": target.name,
                        "email": target.email,
                        "phone": target.phone,
                        "status": target.status,
                        "priority": target.priority,
                        "source_ref": target.source_ref,
                        "email_id": target.email_id,
                        "last_event_at": target.last_event_at.isoformat() if target.last_event_at else None,
                        "events": list(target.events),
                    }
                    for target in targets
                ],
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    _print_table(targets)


def _print_table(targets: list[Any]) -> None:
    headers = ["PRIORITY", "STATUS", "NAME", "PHONE", "EMAIL", "LAST EVENT"]
    rows = [
        [
            target.priority,
            target.status,
            _clip(target.name, 28),
            target.phone or "-",
            _clip(target.email, 34),
            target.last_event_at.strftime("%Y-%m-%d %H:%M") if target.last_event_at else "-",
        ]
        for target in targets
    ]
    widths = [max(len(str(row[idx])) for row in [headers, *rows]) for idx in range(len(headers))]
    print(" | ".join(header.ljust(widths[idx]) for idx, header in enumerate(headers)))
    print("-+-".join("-" * width for width in widths))
    for row in rows:
        print(" | ".join(str(value).ljust(widths[idx]) for idx, value in enumerate(row)))
    print(f"\nTotal: {len(targets)}")


def _clip(value: str, size: int) -> str:
    return value if len(value) <= size else value[: size - 1] + "…"


if __name__ == "__main__":
    main()
