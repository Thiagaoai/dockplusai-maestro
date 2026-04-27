import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from typing import Any

import structlog

from maestro.config import Settings
from maestro.schemas.events import (
    AgentRunRecord,
    ApprovalRequest,
    ApprovalStatus,
    AuditLogRecord,
    LeadRecord,
    ProcessedEvent,
)

log = structlog.get_logger()


class SupabaseStore:
    """Supabase-backed repository for MAESTRO core tables.

    The public methods intentionally match InMemoryStore so the app can switch
    between memory and Supabase via STORAGE_BACKEND without changing agents.
    """

    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self.settings = settings
        self.paused = False
        if client is not None:
            self.client = client
        else:
            if not settings.supabase_url or not settings.supabase_service_key:
                raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY are required")
            from supabase import create_client

            self.client = create_client(settings.supabase_url, settings.supabase_service_key)

    def reset(self) -> None:
        """No-op for production safety.

        Tests should use InMemoryStore or pass a fake client. We never truncate
        production Supabase tables from app code.
        """

    async def is_processed(self, event_id: str) -> bool:
        result = (
            self.client.table("processed_events")
            .select("event_id")
            .eq("event_id", event_id)
            .limit(1)
            .execute()
        )
        return bool(getattr(result, "data", None))

    async def mark_processed(
        self,
        event_id: str,
        source: str,
        result: dict[str, Any],
        business: str | None = None,
    ) -> ProcessedEvent:
        record = ProcessedEvent(event_id=event_id, source=source, business=business, result=result)
        self.client.table("processed_events").upsert(
            record.model_dump(mode="json"),
            on_conflict="event_id",
        ).execute()
        return record

    async def get_processed_result(self, event_id: str) -> dict[str, Any] | None:
        response = (
            self.client.table("processed_events")
            .select("result")
            .eq("event_id", event_id)
            .limit(1)
            .execute()
        )
        rows = getattr(response, "data", None) or []
        return rows[0].get("result") if rows else None

    async def upsert_lead(self, lead: LeadRecord) -> LeadRecord:
        payload = lead.model_dump(mode="json")
        self.client.table("leads").upsert(payload, on_conflict="id").execute()
        return lead

    async def get_lead(self, lead_id: str) -> LeadRecord | None:
        response = (
            self.client.table("leads")
            .select("*")
            .eq("id", lead_id)
            .limit(1)
            .execute()
        )
        rows = getattr(response, "data", None) or []
        return LeadRecord.model_validate(rows[0]) if rows else None

    async def get_lead_by_email(self, email: str) -> LeadRecord | None:
        response = (
            self.client.table("leads")
            .select("*")
            .eq("email", email.casefold())
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = getattr(response, "data", None) or []
        return LeadRecord.model_validate(rows[0]) if rows else None

    async def add_agent_run(self, run: AgentRunRecord) -> AgentRunRecord:
        self.client.table("agent_runs").insert(run.model_dump(mode="json")).execute()
        return run

    async def add_business_metric(self, metric: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "business": metric["business"],
            "metric_type": metric["metric_type"],
            "metric_data": metric["metric_data"],
            "generated_by": metric.get("generated_by"),
            "created_at": datetime.now(UTC).isoformat(),
        }
        self.client.table("business_metrics").insert(payload).execute()
        return metric

    async def upsert_prospect_queue_item(self, item: dict[str, Any]) -> dict[str, Any]:
        self.client.table("prospect_queue").upsert(
            item,
            on_conflict="business,source_type,source_ref",
        ).execute()
        return item

    async def list_prospect_queue(
        self,
        business: str,
        status: str = "queued",
        limit: int = 10,
        source_type: str | None = None,
    ) -> list[dict[str, Any]]:
        query = (
            self.client.table("prospect_queue")
            .select("*")
            .eq("business", business)
            .eq("status", status)
            .order("priority", desc=True)
            .order("created_at", desc=False)
            .limit(limit)
        )
        if source_type:
            query = query.eq("source_type", source_type)
        response = query.execute()
        return getattr(response, "data", None) or []

    async def get_prospect_queue_items_by_refs(
        self,
        business: str,
        source_refs: list[str],
        source_type: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        if not source_refs:
            return []
        query = (
            self.client.table("prospect_queue")
            .select("*")
            .eq("business", business)
            .in_("source_ref", source_refs)
        )
        if source_type:
            query = query.eq("source_type", source_type)
        if status:
            query = query.eq("status", status)
        response = query.execute()
        rows = getattr(response, "data", None) or []
        order = {source_ref: idx for idx, source_ref in enumerate(source_refs)}
        rows.sort(key=lambda item: order.get(item.get("source_ref"), len(order)))
        return rows

    async def update_prospect_queue_status(
        self,
        business: str,
        source_refs: list[str],
        status: str,
    ) -> int:
        updated = 0
        for source_ref in source_refs:
            response = (
                self.client.table("prospect_queue")
                .update({"status": status, "updated_at": datetime.now(UTC).isoformat()})
                .eq("business", business)
                .eq("source_ref", source_ref)
                .execute()
            )
            updated += len(getattr(response, "data", None) or [])
        return updated

    async def count_prospecting_emails_sent_on(self, business: str, day: date) -> int:
        response = (
            self.client.table("audit_log")
            .select("payload,created_at")
            .eq("business", business)
            .eq("agent", "prospecting")
            .eq("action", "prospecting_batch_send_html")
            .order("created_at", desc=True)
            .limit(500)
            .execute()
        )
        total = 0
        for row in getattr(response, "data", None) or []:
            created_at = _parse_datetime(row.get("created_at"))
            if created_at and created_at.date() == day:
                total += int((row.get("payload") or {}).get("sent_count") or 0)
        return total

    async def get_recent_prospecting_sent_emails(self, business: str, days: int = 60) -> set[str]:
        cutoff = datetime.now(UTC) - timedelta(days=days)
        response = (
            self.client.table("audit_log")
            .select("payload,created_at")
            .eq("business", business)
            .eq("agent", "prospecting")
            .eq("action", "prospecting_batch_send_html")
            .order("created_at", desc=True)
            .limit(1000)
            .execute()
        )
        emails: set[str] = set()
        for row in getattr(response, "data", None) or []:
            created_at = _parse_datetime(row.get("created_at"))
            if created_at and created_at < cutoff:
                continue
            for item in (row.get("payload") or {}).get("sent", []):
                email = (item.get("email") or "").casefold()
                if email:
                    emails.add(email)
        return emails

    async def upsert_clients_web_verified(self, item: dict[str, Any]) -> dict[str, Any]:
        payload = {**item, "updated_at": datetime.now(UTC).isoformat()}
        self.client.table("clients_web_verified").upsert(
            payload,
            on_conflict="business,email,campaign",
        ).execute()
        return payload

    async def record_dry_run_action(self, action: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "approval_id": action.get("approval_id"),
            "business": action.get("business"),
            "action": action.get("action", "unknown"),
            "payload": action,
            "created_at": datetime.now(UTC).isoformat(),
        }
        try:
            self.client.table("dry_run_actions").insert(payload).execute()
        except Exception as exc:
            log.warning(
                "supabase_dry_run_actions_persist_failed",
                error=str(exc)[:300],
                action=payload["action"],
            )
        return action

    async def add_audit_log(
        self,
        event_type: str,
        action: str,
        payload: dict[str, Any],
        business: str | None = None,
        agent: str | None = None,
    ) -> AuditLogRecord:
        prev_hash = await self._latest_audit_hash()
        canonical = json.dumps(
            {
                "event_type": event_type,
                "business": business,
                "agent": agent,
                "action": action,
                "payload": payload,
                "prev_hash": prev_hash,
            },
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        record = AuditLogRecord(
            event_type=event_type,
            business=business,
            agent=agent,
            action=action,
            payload=payload,
            prev_hash=prev_hash,
            hash=digest,
        )
        self.client.table("audit_log").insert(record.model_dump(mode="json", exclude={"id"})).execute()
        return record

    async def create_approval(self, approval: ApprovalRequest) -> ApprovalRequest:
        payload = approval.model_dump(mode="json")
        self.client.table("approval_requests").upsert(payload, on_conflict="id").execute()
        return approval

    async def get_approval(self, approval_id: str) -> ApprovalRequest | None:
        response = (
            self.client.table("approval_requests")
            .select("*")
            .eq("id", approval_id)
            .limit(1)
            .execute()
        )
        rows = getattr(response, "data", None) or []
        return ApprovalRequest.model_validate(rows[0]) if rows else None

    async def decide_approval(self, approval_id: str, approved: bool) -> ApprovalRequest | None:
        approval = await self.get_approval(approval_id)
        if not approval:
            return None
        if approval.status != ApprovalStatus.pending:
            return approval
        approval.status = ApprovalStatus.approved if approved else ApprovalStatus.rejected
        approval.decided_at = datetime.now(UTC)
        self.client.table("approval_requests").update(
            {
                "status": approval.status.value,
                "decided_at": approval.decided_at.isoformat(),
            }
        ).eq("id", approval_id).execute()
        return approval

    async def map_approval_to_thread(self, approval_id: str, thread_id: str) -> None:
        try:
            self.client.table("approval_threads").upsert(
                {
                    "approval_id": approval_id,
                    "thread_id": thread_id,
                    "updated_at": datetime.now(UTC).isoformat(),
                },
                on_conflict="approval_id",
            ).execute()
        except Exception as exc:
            log.warning(
                "supabase_approval_thread_map_failed",
                error=str(exc)[:300],
                approval_id=approval_id,
            )

    async def get_thread_for_approval(self, approval_id: str) -> str | None:
        try:
            response = (
                self.client.table("approval_threads")
                .select("thread_id")
                .eq("approval_id", approval_id)
                .limit(1)
                .execute()
            )
            rows = getattr(response, "data", None) or []
            return rows[0].get("thread_id") if rows else None
        except Exception as exc:
            log.warning(
                "supabase_approval_thread_lookup_failed",
                error=str(exc)[:300],
                approval_id=approval_id,
            )
            return None

    async def _latest_audit_hash(self) -> str | None:
        response = (
            self.client.table("audit_log")
            .select("hash")
            .order("id", desc=True)
            .limit(1)
            .execute()
        )
        rows = getattr(response, "data", None) or []
        return rows[0].get("hash") if rows else None


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
