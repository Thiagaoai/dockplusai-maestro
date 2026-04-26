from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from maestro.config import Settings, get_settings
from maestro.profiles import load_profile
from maestro.schemas.events import ApprovalRequest
from maestro.services.composio import ComposioClient, ComposioError
from maestro.services.highlevel import HighLevelClient, HighLevelError
from maestro.services.resend import ResendEmailClient, ResendError
from maestro.utils.contact_policy import find_do_not_contact_match


class DryRunActionExecutor:
    def __init__(
        self,
        store,
        settings: Settings | None = None,
        composio: ComposioClient | None = None,
        highlevel: HighLevelClient | None = None,
        email: ResendEmailClient | None = None,
    ) -> None:
        self.store = store
        self.settings = settings or get_settings()
        self.composio = composio or ComposioClient(self.settings.composio_cli_path)
        self.highlevel = highlevel or HighLevelClient(self.settings)
        self.email = email or ResendEmailClient(self.settings)

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
            if self.settings.dry_run or not self.settings.composio_enabled:
                return await self.execute_sdr_approval(approval)
            return await self.execute_real_sdr_approval(approval)
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

    async def execute_real_sdr_approval(self, approval: ApprovalRequest) -> dict[str, Any]:
        lead = approval.preview.get("lead", {})
        email = approval.preview.get("email", {})
        profile = load_profile(approval.business)
        excluded = find_do_not_contact_match(lead, profile)
        if excluded:
            result = {
                "action": approval.action,
                "approval_id": approval.id,
                "business": approval.business,
                "dry_run": False,
                "status": "skipped",
                "reason": "do_not_contact",
                "details": excluded.reason,
            }
            await self.store.add_audit_log(
                event_type="tool_call",
                business=approval.business,
                agent="sdr",
                action="real_sdr_skipped_do_not_contact",
                payload=result,
            )
            return result

        recipient = lead.get("email")
        if not recipient:
            result = {
                "action": approval.action,
                "approval_id": approval.id,
                "business": approval.business,
                "dry_run": False,
                "status": "skipped",
                "reason": "lead_missing_email",
            }
            await self.store.add_audit_log(
                event_type="tool_call",
                business=approval.business,
                agent="sdr",
                action="real_sdr_skipped_missing_email",
                payload=result,
            )
            return result

        outputs: dict[str, Any] = {"email": None, "calendar": None, "highlevel": None}
        try:
            outputs["email"] = await self.email.send_business_email(
                business=approval.business,
                to=recipient,
                subject=email.get("subject", "Thanks for reaching out"),
                body=email.get("body", ""),
                idempotency_key=f"sdr:{approval.id}:email",
            )

            slots = approval.preview.get("meeting_slots") or []
            if slots:
                outputs["calendar"] = await self.composio.execute(
                    "GOOGLECALENDAR_CREATE_EVENT",
                    self._calendar_payload(slots[0], recipient, lead, profile.business_name),
                )

            outputs["highlevel"] = await self.highlevel.get_pipelines(approval.business)

        except (ComposioError, HighLevelError, ResendError) as exc:
            await self.store.add_audit_log(
                event_type="tool_call",
                business=approval.business,
                agent="sdr",
                action="real_sdr_composio_failed",
                payload={"approval_id": approval.id, "error": str(exc)},
            )
            raise

        result = {
            "action": approval.action,
            "approval_id": approval.id,
            "lead_id": str(approval.lead_id) if approval.lead_id else None,
            "business": approval.business,
            "dry_run": False,
            "status": "executed",
            "tools": outputs,
        }
        await self.store.add_audit_log(
            event_type="tool_call",
            business=approval.business,
            agent="sdr",
            action="real_sdr_follow_up",
            payload=result,
        )
        return result

    def _calendar_payload(
        self, slot: str, recipient: str, lead: dict[str, Any], business_name: str
    ) -> dict[str, Any]:
        start = datetime.fromisoformat(slot.replace("Z", "+00:00"))
        if start.tzinfo is None:
            start = start.replace(tzinfo=ZoneInfo("America/New_York"))
        local_start = start.astimezone(ZoneInfo("America/New_York"))
        local_end = local_start + timedelta(minutes=30)
        lead_name = lead.get("name") or "New lead"
        return {
            "calendar_id": "primary",
            "summary": f"{business_name} consultation - {lead_name}",
            "description": f"MAESTRO approved SDR follow-up for {lead_name}.",
            "start_datetime": local_start.replace(tzinfo=None).isoformat(timespec="seconds"),
            "end_datetime": local_end.replace(tzinfo=None).isoformat(timespec="seconds"),
            "timezone": "America/New_York",
            "attendees": [recipient],
            "send_updates": "all",
            "create_meeting_room": True,
        }
