#!/usr/bin/env python
import argparse
import asyncio
import json

from maestro.repositories import store
from maestro.services.prospecting import import_csv_prospects


async def main() -> None:
    parser = argparse.ArgumentParser(description="Import customer/prospect CSV into MAESTRO leads.")
    parser.add_argument("csv_path", help="Path to the CSV file")
    parser.add_argument("--business", default="roberts", choices=["roberts", "dockplusai"])
    parser.add_argument("--summary", action="store_true", help="Do not print imported event ids")
    args = parser.parse_args()

    result = await import_csv_prospects(args.csv_path, args.business, store)
    payload = result.model_dump()
    if args.summary:
        payload["imported_event_ids"] = {
            "count": len(result.imported_event_ids),
            "sample": result.imported_event_ids[:5],
        }
        payload["skipped"] = {
            "count": len(result.skipped),
            "by_reason": {},
        }
        for skipped in result.skipped:
            reason = skipped.get("reason", "unknown")
            payload["skipped"]["by_reason"][reason] = payload["skipped"]["by_reason"].get(reason, 0) + 1
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
