"""Cost guard and kill switch for MAESTRO agent execution."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog

from maestro.config import Settings
from maestro.memory.redis_session import set_stopped

log = structlog.get_logger()


@dataclass(frozen=True)
class CostSnapshot:
    status: str
    daily_cost_usd: float
    monthly_cost_usd: float
    daily_alert_usd: float
    daily_kill_usd: float
    monthly_kill_usd: float
    reason: str | None = None

    @property
    def should_block(self) -> bool:
        return self.status == "killed"

    def model_dump(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "daily_cost_usd": self.daily_cost_usd,
            "monthly_cost_usd": self.monthly_cost_usd,
            "daily_alert_usd": self.daily_alert_usd,
            "daily_kill_usd": self.daily_kill_usd,
            "monthly_kill_usd": self.monthly_kill_usd,
            "reason": self.reason,
        }


async def evaluate_cost_guard(settings: Settings, store: Any, *, source: str) -> CostSnapshot:
    """Evaluate current spend and pause agents if configured limits are exceeded."""
    daily_cost, monthly_cost = await _current_costs_usd(store)
    snapshot = _snapshot(settings, daily_cost, monthly_cost)

    if snapshot.status == "killed":
        store.paused = True
        set_stopped()
        should_notify = await _audit_once(
            store,
            event_id=_event_id("kill", snapshot.reason),
            action="cost_kill_switch_triggered",
            payload={**snapshot.model_dump(), "source": source},
        )
        if should_notify:
            await _notify_cost_guard(settings, snapshot, source=source)
        log.warning("cost_kill_switch_triggered", **snapshot.model_dump(), source=source)
    elif snapshot.status == "alert":
        should_notify = await _audit_once(
            store,
            event_id=_event_id("alert", datetime.now(UTC).strftime("%Y-%m-%d")),
            action="cost_alert_threshold_crossed",
            payload={**snapshot.model_dump(), "source": source},
        )
        if should_notify:
            await _notify_cost_guard(settings, snapshot, source=source)
        log.warning("cost_alert_threshold_crossed", **snapshot.model_dump(), source=source)
    else:
        log.info("cost_guard_ok", **snapshot.model_dump(), source=source)

    return snapshot


async def _current_costs_usd(store: Any) -> tuple[float, float]:
    if hasattr(store, "agent_runs"):
        return _costs_from_agent_runs(store.agent_runs)
    if hasattr(store, "client"):
        return await _costs_from_supabase(store)
    return 0.0, 0.0


def _costs_from_agent_runs(agent_runs: list[Any]) -> tuple[float, float]:
    now = datetime.now(UTC)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    daily = 0.0
    monthly = 0.0
    for run in agent_runs:
        created_at = getattr(run, "created_at", None)
        if created_at is None:
            continue
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        cost = float(getattr(run, "cost_usd", 0.0) or 0.0)
        if created_at >= month_start:
            monthly += cost
        if created_at >= day_start:
            daily += cost
    return round(daily, 6), round(monthly, 6)


async def _costs_from_supabase(store: Any) -> tuple[float, float]:
    now = datetime.now(UTC)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    try:
        response = (
            store.client.table("agent_runs")
            .select("cost_usd,created_at")
            .gte("created_at", month_start)
            .execute()
        )
        rows = getattr(response, "data", None) or []
    except Exception as exc:
        log.warning("cost_guard_supabase_query_failed", error=str(exc))
        return 0.0, 0.0

    daily = 0.0
    monthly = 0.0
    for row in rows:
        cost = float(row.get("cost_usd") or 0.0)
        monthly += cost
        if str(row.get("created_at") or "") >= day_start:
            daily += cost
    return round(daily, 6), round(monthly, 6)


def _snapshot(settings: Settings, daily_cost: float, monthly_cost: float) -> CostSnapshot:
    if monthly_cost >= settings.monthly_cost_kill_usd:
        return CostSnapshot(
            status="killed",
            daily_cost_usd=daily_cost,
            monthly_cost_usd=monthly_cost,
            daily_alert_usd=settings.daily_cost_alert_usd,
            daily_kill_usd=settings.daily_cost_kill_usd,
            monthly_kill_usd=settings.monthly_cost_kill_usd,
            reason="monthly_cost_kill_usd",
        )
    if daily_cost >= settings.daily_cost_kill_usd:
        return CostSnapshot(
            status="killed",
            daily_cost_usd=daily_cost,
            monthly_cost_usd=monthly_cost,
            daily_alert_usd=settings.daily_cost_alert_usd,
            daily_kill_usd=settings.daily_cost_kill_usd,
            monthly_kill_usd=settings.monthly_cost_kill_usd,
            reason="daily_cost_kill_usd",
        )
    if daily_cost >= settings.daily_cost_alert_usd:
        return CostSnapshot(
            status="alert",
            daily_cost_usd=daily_cost,
            monthly_cost_usd=monthly_cost,
            daily_alert_usd=settings.daily_cost_alert_usd,
            daily_kill_usd=settings.daily_cost_kill_usd,
            monthly_kill_usd=settings.monthly_cost_kill_usd,
            reason="daily_cost_alert_usd",
        )
    return CostSnapshot(
        status="ok",
        daily_cost_usd=daily_cost,
        monthly_cost_usd=monthly_cost,
        daily_alert_usd=settings.daily_cost_alert_usd,
        daily_kill_usd=settings.daily_cost_kill_usd,
        monthly_kill_usd=settings.monthly_cost_kill_usd,
    )


async def _audit_once(store: Any, *, event_id: str, action: str, payload: dict[str, Any]) -> bool:
    if await store.is_processed(event_id):
        return False
    await store.add_audit_log(
        event_type="cost_guard",
        action=action,
        payload=payload,
    )
    await store.mark_processed(event_id, "cost_monitor", payload)
    return True


def _event_id(kind: str, suffix: str | None) -> str:
    return f"cost_monitor:{kind}:{suffix or 'unknown'}"


async def _notify_cost_guard(settings: Settings, snapshot: CostSnapshot, *, source: str) -> None:
    try:
        from maestro.services.telegram import TelegramService

        if snapshot.status == "killed":
            text = (
                "MAESTRO cost kill switch ativado.\n\n"
                f"Motivo: {snapshot.reason}\n"
                f"Custo hoje: ${snapshot.daily_cost_usd:.2f} / ${snapshot.daily_kill_usd:.2f}\n"
                f"Custo mes: ${snapshot.monthly_cost_usd:.2f} / ${snapshot.monthly_kill_usd:.2f}\n"
                f"Fonte: {source}\n\n"
                "Agents pausados. Webhooks continuam ativos."
            )
        else:
            text = (
                "MAESTRO cost alert.\n\n"
                f"Custo hoje: ${snapshot.daily_cost_usd:.2f} / ${snapshot.daily_alert_usd:.2f}\n"
                f"Custo mes: ${snapshot.monthly_cost_usd:.2f}\n"
                f"Fonte: {source}"
            )
        await TelegramService(settings).send_message(text)
    except Exception as exc:
        log.warning("cost_guard_telegram_notify_failed", error=str(exc), source=source)
