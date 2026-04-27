from __future__ import annotations

from typing import Any

from maestro.memory.redis_session import delete_session, get_session, set_session

SESSION_TTL_SECONDS = 900
CONTEXT_TTL_SECONDS = 86_400

_FALLBACK: dict[str, dict[str, Any]] = {}


def _key(chat_id: int, name: str) -> str:
    return f"telegram:{name}:{chat_id}"


def get_chat_session(chat_id: int) -> dict[str, Any]:
    key = _key(chat_id, "session")
    return get_session(key) or _FALLBACK.get(key, {})


def set_chat_session(chat_id: int, data: dict[str, Any], ttl: int = SESSION_TTL_SECONDS) -> None:
    key = _key(chat_id, "session")
    _FALLBACK[key] = data
    set_session(key, data, ttl=ttl)


def clear_chat_session(chat_id: int) -> None:
    key = _key(chat_id, "session")
    _FALLBACK.pop(key, None)
    delete_session(key)


def get_last_context(chat_id: int) -> dict[str, Any]:
    key = _key(chat_id, "last_context")
    return get_session(key) or _FALLBACK.get(key, {})


def set_last_context(chat_id: int, data: dict[str, Any]) -> None:
    key = _key(chat_id, "last_context")
    _FALLBACK[key] = data
    set_session(key, data, ttl=CONTEXT_TTL_SECONDS)

