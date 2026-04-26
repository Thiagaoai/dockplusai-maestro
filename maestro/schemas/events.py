from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ApprovalStatus(StrEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    expired = "expired"


class LeadIn(BaseModel):
    event_id: str
    business: str
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    source: str = "unknown"
    message: str | None = None
    estimated_ticket_usd: float | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class LeadRecord(LeadIn):
    id: UUID = Field(default_factory=uuid4)
    qualification_score: int | None = None
    qualification_reasoning: str | None = None
    status: str = "new"
    thiago_approved: bool = False
    thiago_approved_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AgentRunRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    business: str
    agent_name: str
    input: str
    output: str
    profit_signal: str
    prompt_version: str
    human_approved: bool | None = None
    dry_run: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditLogRecord(BaseModel):
    id: int | None = None
    event_type: str
    business: str | None = None
    agent: str | None = None
    action: str
    payload: dict[str, Any]
    prev_hash: str | None = None
    hash: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ApprovalRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    business: str
    lead_id: UUID | None = None
    event_id: str
    action: str = "sdr_dry_run_follow_up"
    status: ApprovalStatus = ApprovalStatus.pending
    preview: dict[str, Any]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    decided_at: datetime | None = None


class ProcessedEvent(BaseModel):
    event_id: str
    source: str
    business: str | None = None
    result: dict[str, Any]
    processed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AgentResult(BaseModel):
    business: str
    agent_name: str
    status: str = "completed"
    message: str
    data: dict[str, Any] = Field(default_factory=dict)
    approval: ApprovalRequest | None = None
    profit_signal: str
