import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from maestro.schemas.events import (
    AgentRunRecord,
    ApprovalRequest,
    ApprovalStatus,
    AuditLogRecord,
    LeadRecord,
    ProcessedEvent,
)


class InMemoryStore:
    """Test/dev repository mirroring the Supabase core tables."""

    def __init__(self) -> None:
        self.processed_events: dict[str, ProcessedEvent] = {}
        self.leads: dict[str, LeadRecord] = {}
        self.agent_runs: list[AgentRunRecord] = []
        self.audit_log: list[AuditLogRecord] = []
        self.approvals: dict[str, ApprovalRequest] = {}
        self.business_metrics: list[dict[str, Any]] = []
        self.prospect_queue: list[dict[str, Any]] = []
        self.paused: bool = False
        self.dry_run_actions: list[dict[str, Any]] = []
        self.approval_threads: dict[str, str] = {}  # approval_id -> thread_id

    def reset(self) -> None:
        self.__init__()

    async def is_processed(self, event_id: str) -> bool:
        return event_id in self.processed_events

    async def mark_processed(
        self,
        event_id: str,
        source: str,
        result: dict[str, Any],
        business: str | None = None,
    ) -> ProcessedEvent:
        record = ProcessedEvent(
            event_id=event_id,
            source=source,
            business=business,
            result=result,
        )
        self.processed_events[event_id] = record
        return record

    async def get_processed_result(self, event_id: str) -> dict[str, Any] | None:
        record = self.processed_events.get(event_id)
        return record.result if record else None

    async def upsert_lead(self, lead: LeadRecord) -> LeadRecord:
        self.leads[str(lead.id)] = lead
        return lead

    async def get_lead(self, lead_id: str) -> LeadRecord | None:
        return self.leads.get(lead_id)

    async def add_agent_run(self, run: AgentRunRecord) -> AgentRunRecord:
        self.agent_runs.append(run)
        return run

    async def add_business_metric(self, metric: dict[str, Any]) -> dict[str, Any]:
        self.business_metrics.append(metric)
        return metric

    async def upsert_prospect_queue_item(self, item: dict[str, Any]) -> dict[str, Any]:
        for idx, existing in enumerate(self.prospect_queue):
            if (
                existing.get("business") == item.get("business")
                and existing.get("source_type") == item.get("source_type")
                and existing.get("source_ref") == item.get("source_ref")
            ):
                self.prospect_queue[idx] = {**existing, **item}
                return self.prospect_queue[idx]
        self.prospect_queue.append(item)
        return item

    async def add_audit_log(
        self,
        event_type: str,
        action: str,
        payload: dict[str, Any],
        business: str | None = None,
        agent: str | None = None,
    ) -> AuditLogRecord:
        prev_hash = self.audit_log[-1].hash if self.audit_log else None
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
            id=len(self.audit_log) + 1,
            event_type=event_type,
            business=business,
            agent=agent,
            action=action,
            payload=payload,
            prev_hash=prev_hash,
            hash=digest,
        )
        self.audit_log.append(record)
        return record

    async def create_approval(self, approval: ApprovalRequest) -> ApprovalRequest:
        self.approvals[approval.id] = approval
        return approval

    async def get_approval(self, approval_id: str) -> ApprovalRequest | None:
        return self.approvals.get(approval_id)

    async def decide_approval(self, approval_id: str, approved: bool) -> ApprovalRequest | None:
        approval = self.approvals.get(approval_id)
        if not approval:
            return None
        if approval.status != ApprovalStatus.pending:
            return approval
        approval.status = ApprovalStatus.approved if approved else ApprovalStatus.rejected
        approval.decided_at = datetime.now(UTC)
        return approval

    async def map_approval_to_thread(self, approval_id: str, thread_id: str) -> None:
        self.approval_threads[approval_id] = thread_id

    async def get_thread_for_approval(self, approval_id: str) -> str | None:
        return self.approval_threads.get(approval_id)


store = InMemoryStore()
