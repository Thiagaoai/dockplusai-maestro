"""LangGraph state schema for MAESTRO orchestrator."""

from typing import Any, TypedDict


class MaestroState(TypedDict, total=False):
    """Shared state across all graph nodes.

    Fields are optional (total=False) so that partial updates from nodes
    don't require every key on every return.
    """

    business: str
    event_id: str
    input_type: str  # "ghl_lead" | "telegram_message" | "cron"
    input_data: dict[str, Any]
    triage_result: dict[str, Any] | None
    target_agent: str | None
    agent_name: str | None
    agent_message: str | None
    profit_signal: str | None
    agent_output: dict[str, Any] | None
    approval: dict[str, Any] | None  # serialized ApprovalRequest
    human_decision: bool | None
    execution_result: dict[str, Any] | None
    error: str | None
    done: bool
