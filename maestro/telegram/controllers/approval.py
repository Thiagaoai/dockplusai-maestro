from __future__ import annotations

from typing import Any

from maestro.schemas.events import ApprovalStatus


class ApprovalController:
    def __init__(self, store: Any) -> None:
        self.store = store

    async def list_pending(self, limit: int = 8) -> list[dict[str, Any]]:
        if hasattr(self.store, "approvals"):
            return [
                {
                    "id": approval.id,
                    "business": approval.business,
                    "action": approval.action,
                    "created_at": approval.created_at.isoformat(),
                }
                for approval in self.store.approvals.values()
                if approval.status == ApprovalStatus.pending
            ][:limit]
        if hasattr(self.store, "client"):
            response = (
                self.store.client.table("approval_requests")
                .select("id,business,action,created_at")
                .eq("status", "pending")
                .order("created_at", desc=False)
                .limit(limit)
                .execute()
            )
            return getattr(response, "data", None) or []
        return []

