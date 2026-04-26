#!/usr/bin/env python
import argparse
import asyncio
import json

from maestro.agents.hoa_prospecting_graph import build_provincetown_hoa_graph
from maestro.config import get_settings


async def main() -> None:
    parser = argparse.ArgumentParser(description="Send Roberts Provincetown HOA prospecting batch.")
    parser.add_argument("--dry-run", action="store_true", help="Prepare contacts without sending emails.")
    parser.add_argument("--cc", action="append", default=[], help="CC email address. Can be repeated.")
    args = parser.parse_args()

    settings = get_settings()
    cc = args.cc or [settings.resend_reply_to_roberts]
    cc = [email for email in cc if email]
    graph = build_provincetown_hoa_graph()
    result = await graph.ainvoke(
        {
            "business": "roberts",
            "campaign": "provincetown_hoa_web",
            "cc": cc,
            "dry_run": args.dry_run,
        }
    )
    print(
        json.dumps(
            {
                "dry_run": args.dry_run,
                "prepared_count": len(result.get("prepared", [])),
                "sent_count": len(result.get("sent", [])),
                "failed_count": len(result.get("failed", [])),
                "cc": cc,
                "sent_statuses": [item.get("status") for item in result.get("sent", [])],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
