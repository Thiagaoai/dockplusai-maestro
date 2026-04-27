from __future__ import annotations

from typing import Any

from maestro.memory.redis_session import delete_session, get_session, set_session

_FALLBACK: dict[str, dict[str, Any]] = {}


def _key(scope: str, name: str) -> str:
    return f"control:{scope}:{name}"


def set_paused(scope: str, name: str, paused: bool, reason: str | None = None) -> None:
    key = _key(scope, name)
    if paused:
        payload = {"paused": True, "reason": reason or "telegram"}
        _FALLBACK[key] = payload
        set_session(key, payload, ttl=365 * 86_400)
        return
    _FALLBACK.pop(key, None)
    delete_session(key)


def is_paused(scope: str, name: str) -> bool:
    key = _key(scope, name)
    value: dict[str, Any] | None = get_session(key) or _FALLBACK.get(key)
    return bool(value and value.get("paused"))


def paused_items() -> dict[str, list[str]]:
    result = {"agent": [], "business": []}
    for key, value in _FALLBACK.items():
        if not value.get("paused"):
            continue
        parts = key.split(":", 2)
        if len(parts) == 3 and parts[1] in result:
            result[parts[1]].append(parts[2])
    return result

