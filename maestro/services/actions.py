import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from maestro.config import Settings, get_settings
from maestro.profiles import load_profile
from maestro.schemas.events import ApprovalRequest
from maestro.services.composio import ComposioClient, ComposioError
from maestro.services.highlevel import HighLevelClient, HighLevelError
from maestro.services.postforme import PostformeClient, PostformeError
from maestro.services.resend import ResendEmailClient, ResendError
from maestro.utils.contact_policy import find_do_not_contact_match
from maestro.utils.email_validation import is_valid_email_address


class DryRunActionExecutor:
    def __init__(
        self,
        store,
        settings: Settings | None = None,
        composio: ComposioClient | None = None,
        highlevel: HighLevelClient | None = None,
        email: ResendEmailClient | None = None,
        postforme: PostformeClient | None = None,
    ) -> None:
        self.store = store
        self.settings = settings or get_settings()
        self.composio = composio or ComposioClient(self.settings.composio_cli_path)
        self.highlevel = highlevel or HighLevelClient(self.settings)
        self.email = email or ResendEmailClient(self.settings)
        self.postforme = postforme or PostformeClient(self.settings)

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
        await self._record_dry_run_action(result)
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
        if approval.action == "marketing_publish_or_schedule_post" and not self.settings.dry_run:
            return await self.execute_marketing_post(approval)
        if approval.action == "operations_external_action_dry_run" and not self.settings.dry_run:
            return await self.execute_operations_action(approval)
        result = {
            "action": approval.action,
            "approval_id": approval.id,
            "lead_id": str(approval.lead_id) if approval.lead_id else None,
            "business": approval.business,
            "dry_run": True,
            "preview": approval.preview,
        }
        await self._record_dry_run_action(result)
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
        await self._record_dry_run_action(result)
        await self.store.add_audit_log(
            event_type="tool_call",
            business=approval.business,
            agent="prospecting",
            action="dry_run_prospecting_batch_send_html",
            payload=result,
        )
        return result

    async def _record_dry_run_action(self, result: dict[str, Any]) -> None:
        if hasattr(self.store, "record_dry_run_action"):
            await self.store.record_dry_run_action(result)
        elif hasattr(self.store, "dry_run_actions"):
            self.store.dry_run_actions.append(result)

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
        remaining_capacity = await self._remaining_prospecting_send_capacity(approval.business)

        for prospect in approval.preview.get("prospects", []):
            if approval.business == "roberts" and len(sent) >= remaining_capacity:
                skipped.append({"source_ref": prospect.get("source_ref"), "reason": "daily_send_limit_reached"})
                continue
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
            if not is_valid_email_address(lead.email):
                skipped.append({"source_ref": source_ref, "email": lead.email, "reason": "invalid_email"})
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
            await asyncio.sleep(0.25)
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

    async def _remaining_prospecting_send_capacity(self, business: str) -> int:
        if business != "roberts":
            return 10_000
        limit = self.settings.prospecting_daily_send_limit_roberts
        if limit <= 0 or not hasattr(self.store, "count_prospecting_emails_sent_on"):
            return 10_000
        sent_today = await self.store.count_prospecting_emails_sent_on(
            business,
            datetime.now(UTC).date(),
        )
        return max(0, limit - sent_today)

    async def execute_marketing_post(self, approval: ApprovalRequest) -> dict[str, Any]:
        preview = approval.preview
        caption = "\n\n".join(
            part
            for part in [
                preview.get("caption", ""),
                " ".join(preview.get("hashtags") or []),
            ]
            if part
        )
        try:
            post_result = await self.postforme.publish_or_schedule(
                business=approval.business,
                caption=caption,
                image_url=preview.get("image_url") or preview.get("media_url"),
                platform=preview.get("platform", "instagram"),
                scheduled_at=preview.get("scheduled_at"),
                idempotency_key=f"marketing:{approval.id}",
            )
        except PostformeError as exc:
            await self.store.add_audit_log(
                event_type="tool_call",
                business=approval.business,
                agent="marketing",
                action="postforme_failed",
                payload={"approval_id": approval.id, "error": str(exc)},
            )
            raise

        result = {
            "action": approval.action,
            "approval_id": approval.id,
            "business": approval.business,
            "dry_run": False,
            "status": post_result.get("status"),
            "tool": "postforme",
            "result": post_result,
        }
        await self.store.add_audit_log(
            event_type="tool_call",
            business=approval.business,
            agent="marketing",
            action="marketing_publish_or_schedule_post",
            payload=result,
        )
        return result

    async def execute_operations_action(self, approval: ApprovalRequest) -> dict[str, Any]:
        prepared = approval.preview.get("prepared", {})
        kind = prepared.get("kind")
        try:
            if kind == "calendar":
                tool_result = await self._execute_calendar_operation(approval, prepared)
            elif kind == "pipeline":
                tool_result = await self.highlevel.move_opportunity_stage(
                    approval.business,
                    prepared.get("opportunity_id", ""),
                    prepared.get("stage_id", ""),
                )
            elif kind == "follow_up":
                tool_result = await self._execute_follow_up_operation(approval, prepared)
            else:
                tool_result = {"status": "skipped", "reason": "unsupported_operation_kind", "kind": kind}
        except (ComposioError, HighLevelError, ResendError, ValueError) as exc:
            await self.store.add_audit_log(
                event_type="tool_call",
                business=approval.business,
                agent="operations",
                action="operations_external_action_failed",
                payload={"approval_id": approval.id, "kind": kind, "error": str(exc)},
            )
            raise

        result = {
            "action": approval.action,
            "approval_id": approval.id,
            "business": approval.business,
            "dry_run": False,
            "status": tool_result.get("status", "ok"),
            "kind": kind,
            "result": tool_result,
        }
        await self.store.add_audit_log(
            event_type="tool_call",
            business=approval.business,
            agent="operations",
            action="operations_external_action",
            payload=result,
        )
        return result

    async def _execute_calendar_operation(
        self,
        approval: ApprovalRequest,
        prepared: dict[str, Any],
    ) -> dict[str, Any]:
        start = prepared.get("start_datetime") or prepared.get("start")
        if not start:
            return {"status": "skipped", "reason": "missing_calendar_start"}
        return await self.composio.execute(
            "GOOGLECALENDAR_CREATE_EVENT",
            {
                "calendar_id": prepared.get("calendar_id", "primary"),
                "summary": prepared.get("summary") or approval.preview.get("task") or "MAESTRO task",
                "description": prepared.get("description") or "Created after Thiago approval in MAESTRO.",
                "start_datetime": start,
                "end_datetime": prepared.get("end_datetime") or prepared.get("end"),
                "timezone": prepared.get("timezone") or self.settings.prospecting_schedule_timezone,
                "attendees": prepared.get("attendees") or [],
                "send_updates": prepared.get("send_updates", "all"),
            },
        )

    async def _execute_follow_up_operation(
        self,
        approval: ApprovalRequest,
        prepared: dict[str, Any],
    ) -> dict[str, Any]:
        recipient = prepared.get("to") or prepared.get("email")
        if not recipient:
            return {"status": "skipped", "reason": "missing_follow_up_recipient"}
        return await self.email.send_business_email(
            business=approval.business,
            to=recipient,
            subject=prepared.get("subject", "Following up"),
            body=prepared.get("body") or prepared.get("draft") or "",
            idempotency_key=f"operations:{approval.id}:follow-up",
        )

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

        outputs: dict[str, Any] = {"email": None, "calendar": None, "ghl_contact": None, "ghl_opportunity": None}
        try:
            # 1. Create GHL contact
            from maestro.tools.ghl import create_contact, create_opportunity, move_opportunity_stage

            name = lead.get("name") or "New Lead"
            name_parts = name.split(maxsplit=1)
            first_name = name_parts[0] if name_parts else "New"
            last_name = name_parts[1] if len(name_parts) > 1 else "Lead"

            outputs["ghl_contact"] = await create_contact(
                business_id=approval.business,
                first_name=first_name,
                last_name=last_name,
                email=recipient,
                phone=lead.get("phone"),
                source=lead.get("source", "maestro_sdr"),
                tags=["maestro", "sdr_inbound"],
                idempotency_key=f"sdr:{approval.id}:ghl_contact",
            )

            # 2. Create GHL opportunity
            contact_id = outputs["ghl_contact"].get("contact_id")
            if contact_id:
                outputs["ghl_opportunity"] = await create_opportunity(
                    business_id=approval.business,
                    contact_id=contact_id,
                    name=f"{name} — SDR inbound",
                    monetary_value=lead.get("estimated_ticket_usd") or 0,
                    idempotency_key=f"sdr:{approval.id}:ghl_opportunity",
                )

                # 3. Move to "contacted" stage
                opp_id = outputs["ghl_opportunity"].get("opportunity_id")
                if opp_id:
                    await move_opportunity_stage(
                        business_id=approval.business,
                        opportunity_id=opp_id,
                        stage_name="contacted",
                    )

            # 4. Send email via Resend
            outputs["email"] = await self.email.send_business_email(
                business=approval.business,
                to=recipient,
                subject=email.get("subject", "Thanks for reaching out"),
                body=email.get("body", ""),
                idempotency_key=f"sdr:{approval.id}:email",
            )

            # 5. Create calendar event
            slots = approval.preview.get("meeting_slots") or []
            if slots:
                outputs["calendar"] = await self.composio.execute(
                    "GOOGLECALENDAR_CREATE_EVENT",
                    self._calendar_payload(slots[0], recipient, lead, profile.business_name),
                )

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
