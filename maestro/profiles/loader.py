import json
from functools import lru_cache
from pathlib import Path

from maestro.config import get_settings
from maestro.profiles._schema import BusinessProfile


@lru_cache
def load_profile(business: str) -> BusinessProfile:
    settings = get_settings()
    path = Path(settings.profile_dir) / f"{business}.json"
    if not path.exists():
        raise ValueError(f"profile_not_found:{business}")
    return BusinessProfile.model_validate(json.loads(path.read_text(encoding="utf-8")))
