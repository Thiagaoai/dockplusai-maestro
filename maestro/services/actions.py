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
        if approval.action == "prospecting_batch_send_html":
            if self.settings.dry_run and not approval.preview.get("force_real_send"):
                return await self.execute_prospecting_batch_dry_run(approval)
            return await self.execute_prospecting_batch(approval)
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

    async def execute_prospecting_batch_dry_run(self, approval: ApprovalRequest) -> dict[str, Any]:
        source_refs = approval.preview.get("source_refs", [])
        result = {
            "action": approval.action,
            "approval_id": approval.id,
            "business": approval.business,
            "dry_run": True,
            "would_send_count": len(approval.preview.get("prospects", [])),
            "subject": approval.preview.get("email", {}).get("subject"),
            "source_refs": source_refs,
        }
        if hasattr(self.store, "dry_run_actions"):
            self.store.dry_run_actions.append(result)
        await self.store.add_audit_log(
            event_type="tool_call",
            business=approval.business,
            agent="prospecting",
            action="dry_run_prospecting_batch_send_html",
            payload=result,
        )
        return result

    async def execute_prospecting_batch(self, approval: ApprovalRequest) -> dict[str, Any]:
        profile = load_profile(approval.business)
        email = approval.preview.get("email", {})
        sent: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        failed: list[dict[str, Any]] = []
        table_errors: list[dict[str, Any]] = []
        sent_refs: list[str] = []
        failed_refs: list[str] = []
        attempted_count = len(approval.preview.get("prospects", []))
        campaign = approval.preview.get("campaign", {})
        cc = email.get("cc") or []

        for prospect in approval.preview.get("prospects", []):
            source_ref = prospect.get("source_ref")
            lead_id = prospect.get("lead_id")
            lead = await self.store.get_lead(lead_id) if lead_id else None
            if not lead:
                skipped.append({"source_ref": source_ref, "reason": "lead_not_found"})
                continue
            lead_data = lead.model_dump(mode="json")
            excluded = find_do_not_contact_match(lead_data, profile)
            if excluded:
                skipped.append({"source_ref": source_ref, "reason": "do_not_contact"})
                continue
            if not lead.email:
                skipped.append({"source_ref": source_ref, "reason": "missing_email"})
                continue

            try:
                result = await self.email.send_business_email(
                    business=approval.business,
                    to=lead.email,
                    cc=cc,
                    subject=email.get("subject", "Roberts Landscape offer"),
                    body=email.get("text", ""),
                    html=email.get("html"),
                    idempotency_key=f"prospecting:{approval.id}:{source_ref}",
                )
            except ResendError as exc:
                failed.append({"source_ref": source_ref, "email": lead.email, "reason": str(exc)[:300]})
                if source_ref:
                    failed_refs.append(source_ref)
                continue

            sent_item = {
                "source_ref": source_ref,
                "email": lead.email,
                "email_id": result.get("email_id"),
                "property_name": prospect.get("property_name") or lead.name,
            }
            sent.append(sent_item)
            if source_ref:
                sent_refs.append(source_ref)
            if prospect.get("source_type") == "scrape" and hasattr(self.store, "upsert_clients_web_verified"):
                raw = lead.raw or {}
                try:
                    await self.store.upsert_clients_web_verified(
                        {
                            "business": approval.business,
                            "lead_id": str(lead.id),
                            "property_name": prospect.get("property_name") or lead.name or "Unknown",
                            "email": lead.email,
                            "source_name": prospect.get("source_name") or lead.source or "scrape",
                            "source_ref": source_ref,
                            "source_url": prospect.get("source_url") or raw.get("source_url"),
                            "verification_note": prospect.get("verification_note") or raw.get("verification"),
                            "campaign": campaign.get("flow") or campaign.get("name") or "web_verified",
                            "approval_id": approval.id,
                            "email_id": result.get("email_id"),
                            "send_status": "sent",
                            "payload": {
                                "prospect": prospect,
                                "lead_raw": raw,
                            },
                        }
                    )
                except Exception as exc:
                    table_errors.append(
                        {
                            "source_ref": source_ref,
                            "email": lead.email,
                            "table": "clients_web_verified",
                            "error": str(exc)[:300],
                        }
                    )

        if sent_refs and hasattr(self.store, "update_prospect_queue_status"):
            await self.store.update_prospect_queue_status(approval.business, sent_refs, "sent")
        skipped_refs = [item["source_ref"] for item in skipped if item.get("source_ref")]
        if skipped_refs and hasattr(self.store, "update_prospect_queue_status"):
            await self.store.update_prospect_queue_status(approval.business, skipped_refs, "skipped")
        if failed_refs and hasattr(self.store, "update_prospect_queue_status"):
            await self.store.update_prospect_queue_status(approval.business, failed_refs, "failed")

        result = {
            "action": approval.action,
            "approval_id": approval.id,
            "business": approval.business,
            "dry_run": False,
            "status": "executed",
            "attempted_count": attempted_count,
            "sent_count": len(sent),
            "skipped_count": len(skipped),
            "failed_count": len(failed),
            "table_error_count": len(table_errors),
            "sent": sent,
            "skipped": skipped,
            "failed": failed,
            "table_errors": table_errors,
        }
        await self.store.add_audit_log(
            event_type="tool_call",
            business=approval.business,
            agent="prospecting",
            action="prospecting_batch_send_html",
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
