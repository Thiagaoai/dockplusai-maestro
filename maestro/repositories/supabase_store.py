import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from maestro.config import Settings
from maestro.schemas.events import (
    AgentRunRecord,
    ApprovalRequest,
    ApprovalStatus,
    AuditLogRecord,
    LeadRecord,
    ProcessedEvent,
)


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
