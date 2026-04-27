from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from maestro.config import Settings
from maestro.memory.redis_session import is_stopped
from maestro.repositories.store import InMemoryStore
from maestro.services.cost_monitor import evaluate_cost_guard
from maestro.services.call_targets import load_call_targets
from maestro.telegram.control_state import paused_items
from maestro.telegram.registry import AGENT_REGISTRY


class StatusController:
    def __init__(self, settings: Settings, store: Any) -> None:
        self.settings = settings
        self.store = store

    async def system_status(self) -> dict:
        snapshot = await evaluate_cost_guard(self.settings, self.store, source="telegram_status")
        return {
            "env": self.settings.app_env,
            "dry_run": self.settings.dry_run,
            "storage_backend": self.settings.storage_backend,
            "paused": bool(getattr(self.store, "paused", False) or is_stopped()),
            "daily_cost_usd": snapshot.daily_cost_usd,
            "daily_alert_usd": snapshot.daily_alert_usd,
            "pending_approvals": await self._pending_count(),
            "recent_errors": await self._recent_errors_count(),
        }

    async def cost_status(self) -> dict:
        snapshot = await evaluate_cost_guard(self.settings, self.store, source="telegram_costs")
        return snapshot.model_dump()

    async def agents(self) -> dict:
        return {
            "agents": [
                {
                    "name": name,
                    "aliases": list(spec.aliases),
                    "subagents": list(spec.subagents),
                    "workflows": list(spec.workflows.keys()),
                }
                for name, spec in AGENT_REGISTRY.items()
            ],
            "paused": paused_items(),
        }

    async def recent_errors(self) -> list[dict[str, Any]]:
        if hasattr(self.store, "audit_log"):
            since = datetime.now(UTC) - timedelta(hours=24)
            return [
                item.model_dump(mode="json")
                for item in self.store.audit_log
                if item.created_at >= since and ("error" in item.action or "failed" in item.action)
            ][-8:]
        if hasattr(self.store, "client"):
            response = (
                self.store.client.table("audit_log")
                .select("agent,action,created_at,payload")
                .or_("action.ilike.%error%,action.ilike.%failed%")
                .order("created_at", desc=True)
                .limit(8)
                .execute()
            )
            return getattr(response, "data", None) or []
        return []

    async def call_targets(self, business: str = "roberts", days: int = 1, limit: int = 10) -> list[dict[str, Any]]:
        targets = await load_call_targets(self.store, business=business, days=days, limit=limit)
        return [
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
        ]

    async def _pending_count(self) -> int:
        if hasattr(self.store, "approvals"):
            return sum(1 for approval in self.store.approvals.values() if approval.status == "pending")
        if hasattr(self.store, "client"):
            response = (
                self.store.client.table("approval_requests")
                .select("id")
                .eq("status", "pending")
                .execute()
            )
            return len(getattr(response, "data", None) or [])
        return 0

    async def _recent_errors_count(self) -> int:
        return len(await self.recent_errors())
