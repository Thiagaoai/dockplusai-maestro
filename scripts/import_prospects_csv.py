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
    args = parser.parse_args()

    result = await import_csv_prospects(args.csv_path, args.business, store)
    print(json.dumps(result.model_dump(), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
