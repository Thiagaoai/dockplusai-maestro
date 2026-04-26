"""
Redis session layer.

Provides two things:
1. Persistent /stop flag — survives container restarts, unlike InMemoryStore.paused
2. Distributed cron lock — prevents APScheduler firing twice on multi-replica deploys.

Usage:
    from maestro.memory.redis_session import get_redis, is_stopped, set_stopped, clear_stopped

Falls back gracefully when Redis is unavailable (log warning, don't crash).
"""

import json
import logging
from typing import Any

import structlog

log = structlog.get_logger()

STOPPED_KEY = "maestro:stopped"
SESSION_TTL = 3600  # 1h


def _make_client():
    try:
        import redis

        from maestro.config import get_settings

        settings = get_settings()
        return redis.from_url(settings.redis_url, decode_responses=True)
    except Exception as exc:  # pragma: no cover
        log.warning("redis_client_init_failed", error=str(exc))
        return None


_client = None


def get_redis():
    global _client
    if _client is None:
        _client = _make_client()
    return _client


# ── stop / start ──────────────────────────────────────────────────────────────

def is_stopped() -> bool:
    """Return True if /stop is active. Falls back to False if Redis is down."""
    r = get_redis()
    if r is None:
        return False
    try:
        return bool(r.exists(STOPPED_KEY))
    except Exception as exc:
        log.warning("redis_is_stopped_failed", error=str(exc))
        return False


def set_stopped() -> None:
    r = get_redis()
    if r is None:
        return
    try:
        r.set(STOPPED_KEY, "1")
        log.info("maestro_stopped_redis")
    except Exception as exc:
        log.warning("redis_set_stopped_failed", error=str(exc))


def clear_stopped() -> None:
    r = get_redis()
    if r is None:
        return
    try:
        r.delete(STOPPED_KEY)
        log.info("maestro_started_redis")
    except Exception as exc:
        log.warning("redis_clear_stopped_failed", error=str(exc))


# ── distributed cron lock ─────────────────────────────────────────────────────

def acquire_cron_lock(job_name: str, timeout: int = 300) -> bool:
    """
    Try to acquire an exclusive lock for a cron job.

    Returns True if lock acquired (this instance should run).
    Returns False if another instance already holds it.

    Without this, APScheduler on multi-replica or after a fast restart
    fires CFO/CMO/CEO twice — see CLAUDE.md gotchas.
    """
    r = get_redis()
    if r is None:
        return True  # no Redis, assume single instance, proceed
    try:
        key = f"cron:lock:{job_name}"
        acquired = r.set(key, "1", nx=True, ex=timeout)
        if not acquired:
            log.info("cron_lock_already_held", job=job_name)
        return bool(acquired)
    except Exception as exc:
        log.warning("redis_cron_lock_failed", job=job_name, error=str(exc))
        return True  # fail open: better to run twice than not at all


def release_cron_lock(job_name: str) -> None:
    r = get_redis()
    if r is None:
        return
    try:
        r.delete(f"cron:lock:{job_name}")
    except Exception as exc:
        log.warning("redis_cron_lock_release_failed", job=job_name, error=str(exc))


# ── generic session cache ──────────────────────────────────────────────────────

def get_session(thread_id: str) -> dict[str, Any] | None:
    r = get_redis()
    if r is None:
        return None
    try:
        raw = r.get(f"session:{thread_id}")
        return json.loads(raw) if raw else None
    except Exception as exc:
        log.warning("redis_get_session_failed", thread_id=thread_id, error=str(exc))
        return None


def set_session(thread_id: str, data: dict[str, Any], ttl: int = SESSION_TTL) -> None:
    r = get_redis()
    if r is None:
        return
    try:
        r.setex(f"session:{thread_id}", ttl, json.dumps(data, default=str))
    except Exception as exc:
        log.warning("redis_set_session_failed", thread_id=thread_id, error=str(exc))


def delete_session(thread_id: str) -> None:
    r = get_redis()
    if r is None:
        return
    try:
        r.delete(f"session:{thread_id}")
    except Exception as exc:
        log.warning("redis_delete_session_failed", thread_id=thread_id, error=str(exc))
