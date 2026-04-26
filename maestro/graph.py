"""MAESTRO LangGraph orchestrator with Redis checkpointing and HITL.

Replaces the deterministic MaestroOrchestrator shell with a StateGraph
that uses interrupt() for human-in-the-loop approvals.
"""

from typing import Any

import structlog
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from maestro.config import Settings
from maestro.graph_nodes import (
    execute_node,
    finalize_node,
    hitl_node,
    phase1_agent_node,
    sdr_node,
    triage_node,
)
from maestro.graph_state import MaestroState
from maestro.repositories.store import InMemoryStore
from maestro.schemas.events import LeadIn

log = structlog.get_logger()


_checkpointer_singleton: BaseCheckpointSaver | None = None


def _make_checkpointer(settings: Settings) -> BaseCheckpointSaver:
    """Return an appropriate checkpointer for the current environment.

    Uses a singleton so that HITL resume finds the same checkpoint data.
    """
    global _checkpointer_singleton
    if _checkpointer_singleton is not None:
        return _checkpointer_singleton

    if settings.app_env in ("test", "dev"):
        from langgraph.checkpoint.memory import MemorySaver

        _checkpointer_singleton = MemorySaver()
    else:
        from langgraph.checkpoint.redis import RedisSaver

        _checkpointer_singleton = RedisSaver.from_conn_string(settings.redis_url)

    return _checkpointer_singleton


def clear_checkpointer() -> None:
    """Reset the singleton (used by tests)."""
    global _checkpointer_singleton
    _checkpointer_singleton = None


def _route_after_triage(state: MaestroState) -> str:
    """Conditional edge: which agent node to run after triage."""
    target = state.get("target_agent")
    if target == "sdr":
        return "sdr"
    return "phase1_agent"


def _route_after_hitl(state: MaestroState) -> str:
    """Conditional edge: execute if approved, skip if rejected."""
    # When coming back from interrupt, human_decision is set by the resume
    if state.get("human_decision") is True:
        return "execute"
    return "finalize"


class MaestroGraph:
    """LangGraph-based orchestrator.

    Public API is kept compatible with the old MaestroOrchestrator so
    that webhooks don't need to change.
    """

    def __init__(
        self,
        settings: Settings,
        store: InMemoryStore,
        checkpointer: BaseCheckpointSaver | None = None,
    ) -> None:
        self.settings = settings
        self.store = store
        self.checkpointer = checkpointer or _make_checkpointer(settings)
        self._graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        builder = StateGraph(MaestroState)

        # Nodes
        builder.add_node("triage", triage_node)
        builder.add_node("sdr", sdr_node)
        builder.add_node("phase1_agent", phase1_agent_node)
        builder.add_node("hitl", hitl_node)
        builder.add_node("execute", execute_node)
        builder.add_node("finalize", finalize_node)

        # Edges
        builder.add_edge(START, "triage")
        builder.add_conditional_edges("triage", _route_after_triage)
        builder.add_edge("sdr", "hitl")
        builder.add_conditional_edges(
            "phase1_agent",
            lambda state: "hitl" if state.get("approval") else "finalize",
        )
        builder.add_conditional_edges("hitl", _route_after_hitl)
        builder.add_edge("execute", "finalize")
        builder.add_edge("finalize", END)

        return builder.compile(checkpointer=self.checkpointer)

    async def handle_inbound_lead(self, lead_in: LeadIn) -> dict[str, Any]:
        """Entry point for GHL webhooks."""
        # Idempotency check
        if await self.store.is_processed(lead_in.event_id):
            return {
                "status": "duplicate",
                "event_id": lead_in.event_id,
                "result": await self.store.get_processed_result(lead_in.event_id),
            }

        thread_id = f"ghl:{lead_in.event_id}"
        initial_state: MaestroState = {
            "business": lead_in.business,
            "event_id": lead_in.event_id,
            "input_type": "ghl_lead",
            "input_data": lead_in.model_dump(mode="json"),
        }

        config = {"configurable": {"thread_id": thread_id}}
        result = await self._graph.ainvoke(initial_state, config=config)

        # If we hit an interrupt, record the mapping so Telegram can resume
        if result.get("__interrupt__"):
            approval = result.get("approval")
            if approval:
                await self.store.map_approval_to_thread(approval["id"], thread_id)
            response = {
                "status": "approval_requested",
                "event_id": lead_in.event_id,
                "thread_id": thread_id,
                "approval_id": approval["id"] if approval else None,
                "dry_run": self.settings.dry_run,
            }
            await self.store.mark_processed(lead_in.event_id, "ghl", response, business=lead_in.business)
            return response

        response = {
            "status": "completed",
            "event_id": lead_in.event_id,
            "thread_id": thread_id,
            "result": result,
        }
        await self.store.mark_processed(lead_in.event_id, "ghl", response, business=lead_in.business)
        return response

    async def handle_text_message(self, text: str, last_business: str = "roberts") -> dict[str, Any]:
        """Entry point for Telegram messages (non-command)."""
        event_id = f"telegram:{hash(text)}"
        thread_id = f"telegram:{event_id}"
        initial_state: MaestroState = {
            "business": last_business,
            "event_id": event_id,
            "input_type": "telegram_message",
            "input_data": {"text": text, "last_business": last_business},
        }

        config = {"configurable": {"thread_id": thread_id}}
        result = await self._graph.ainvoke(initial_state, config=config)

        if result.get("__interrupt__"):
            approval = result.get("approval")
            if approval:
                await self.store.map_approval_to_thread(approval["id"], thread_id)
            return {
                "status": "approval_requested",
                "thread_id": thread_id,
                "approval_id": approval["id"] if approval else None,
                "route": result.get("triage_result"),
                "agent": result.get("agent_name"),
                "business": result.get("business"),
                "message": result.get("agent_message"),
                "profit_signal": result.get("profit_signal"),
            }

        return {
            "status": "completed",
            "thread_id": thread_id,
            "route": result.get("triage_result"),
            "agent": result.get("agent_name"),
            "business": result.get("business"),
            "message": result.get("agent_message"),
            "profit_signal": result.get("profit_signal"),
            "telegram": {"dry_run": True, "payload": {"text": result.get("agent_message", "")}},
            "result": result,
        }

    async def resume(self, thread_id: str, decision: bool) -> dict[str, Any]:
        """Resume a paused graph after human approval/rejection.

        Called from Telegram approval callbacks.
        """
        config = {"configurable": {"thread_id": thread_id}}
        result = await self._graph.ainvoke(Command(resume=decision), config=config)
        return {
            "status": "completed" if result.get("done") else "unknown",
            "thread_id": thread_id,
            "result": result,
        }
