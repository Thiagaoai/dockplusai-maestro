from typing import Any

from maestro.schemas.events import ApprovalRequest


class DryRunActionExecutor:
    def __init__(self, store) -> None:
        self.store = store

    async def execute_sdr_approval(self, approval: ApprovalRequest) -> dict[str, Any]:
        result = {
            "action": approval.action,
            "approval_id": approval.id,
            "lead_id": str(approval.lead_id),
            "business": approval.business,
            "dry_run": True,
            "would_send_email": approval.preview.get("email"),
            "would_offer_slots": approval.preview.get("meeting_slots", []),
            "would_move_ghl_pipeline": True,
        }
        if hasattr(self.store, "dry_run_actions"):
            self.store.dry_run_actions.append(result)
        await self.store.add_audit_log(
            event_type="tool_call",
            business=approval.business,
            agent="sdr",
            action="dry_run_sdr_follow_up",
            payload=result,
        )
        return result

    async def execute_approval(self, approval: ApprovalRequest) -> dict[str, Any]:
        if approval.action == "sdr_dry_run_follow_up":
            return await self.execute_sdr_approval(approval)
        result = {
            "action": approval.action,
            "approval_id": approval.id,
            "lead_id": str(approval.lead_id) if approval.lead_id else None,
            "business": approval.business,
            "dry_run": True,
            "preview": approval.preview,
        }
        if hasattr(self.store, "dry_run_actions"):
            self.store.dry_run_actions.append(result)
        await self.store.add_audit_log(
            event_type="tool_call",
            business=approval.business,
            agent=approval.action.split("_", 1)[0],
            action=f"dry_run_{approval.action}",
            payload=result,
        )
        return result
