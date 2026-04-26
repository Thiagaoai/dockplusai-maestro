import asyncio
import json

from maestro.config import get_settings
from maestro.repositories import store
from maestro.services.cost_monitor import evaluate_cost_guard


async def _main() -> dict:
    settings = get_settings()
    snapshot = await evaluate_cost_guard(settings, store, source="script")
    return snapshot.model_dump()


def main() -> None:
    print(json.dumps(asyncio.run(_main()), sort_keys=True))


if __name__ == "__main__":
    main()
