#!/usr/bin/env python3
"""List Roberts prospecting contacts to call after Resend delivery events."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from maestro.config import get_settings
from maestro.repositories.supabase_store import SupabaseStore
from maestro.services.call_targets import build_call_targets, source_refs_from_send_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="List prospecting contacts ready for phone follow-up.")
    parser.add_argument("--business", default="roberts")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--json", action="store_true", help="Print JSON instead of a table.")
    args = parser.parse_args()

    settings = get_settings()
    store = SupabaseStore(settings)
    send_rows = _fetch_audit_rows(
        store,
        business=args.business,
        action="prospecting_batch_send_html",
        days=args.days,
        limit=max(args.limit * 4, 100),
    )
    event_rows = _fetch_audit_rows(
        store,
        business=args.business,
        action="resend_email_event",
        days=args.days,
        limit=max(args.limit * 20, 500),
    )
    leads_by_source_ref = _fetch_leads_by_source_ref(store, args.business, source_refs_from_send_rows(send_rows))
    targets = build_call_targets(send_rows, event_rows, leads_by_source_ref, limit=args.limit)

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


def _fetch_audit_rows(
    store: SupabaseStore,
    business: str,
    action: str,
    days: int,
    limit: int,
) -> list[dict[str, Any]]:
    cutoff = datetime.now(UTC) - timedelta(days=days)
    response = (
        store.client.table("audit_log")
        .select("payload,created_at")
        .eq("business", business)
        .eq("agent", "prospecting")
        .eq("action", action)
        .gte("created_at", cutoff.isoformat())
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return getattr(response, "data", None) or []


def _fetch_leads_by_source_ref(
    store: SupabaseStore,
    business: str,
    source_refs: list[str],
) -> dict[str, dict[str, Any]]:
    if not source_refs:
        return {}
    queue_rows: list[dict[str, Any]] = []
    for chunk in _chunks(source_refs, 100):
        response = (
            store.client.table("prospect_queue")
            .select("source_ref,lead_id")
            .eq("business", business)
            .in_("source_ref", chunk)
            .execute()
        )
        queue_rows.extend(getattr(response, "data", None) or [])

    lead_ids = [row["lead_id"] for row in queue_rows if row.get("lead_id")]
    leads_by_id: dict[str, dict[str, Any]] = {}
    for chunk in _chunks(lead_ids, 100):
        response = (
            store.client.table("leads")
            .select("id,name,email,phone")
            .in_("id", chunk)
            .execute()
        )
        for row in getattr(response, "data", None) or []:
            leads_by_id[str(row.get("id"))] = row

    return {
        row["source_ref"]: leads_by_id.get(str(row.get("lead_id")), {})
        for row in queue_rows
        if row.get("source_ref")
    }


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


def _chunks(values: list[str], size: int) -> list[list[str]]:
    return [values[idx : idx + size] for idx in range(0, len(values), size)]


def _clip(value: str, size: int) -> str:
    return value if len(value) <= size else value[: size - 1] + "…"


if __name__ == "__main__":
    main()
