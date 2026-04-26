"""LangGraph node functions for MAESTRO orchestrator.

Each node receives the current MaestroState and returns a partial dict
with the fields it wants to update.
"""

from typing import Any

import structlog
from langgraph.types import interrupt

from maestro.agents.ceo import CEOAgent
from maestro.agents.cfo import CFOAgent
from maestro.agents.cmo import CMOAgent
from maestro.agents.marketing import MarketingAgent
from maestro.agents.operations import OperationsAgent
from maestro.agents.prospecting import ProspectingAgent
from maestro.agents.sdr import SDRAgent
from maestro.agents.triage import triage_message
from maestro.config import Settings
from maestro.profiles import load_profile
from maestro.repositories import store
from maestro.schemas.events import ApprovalRequest, LeadIn
from maestro.services.actions import DryRunActionExecutor
from maestro.services.cost_monitor import evaluate_cost_guard
from maestro.services.telegram import TelegramService
from maestro.utils.langsmith import trace_agent_run

log = structlog.get_logger()


def _settings() -> Settings:
    from maestro.config import get_settings

    return get_settings()


async def cost_guard_node(state: dict[str, Any]) -> dict[str, Any]:
    """Check cost thresholds before any agent executes."""
    settings = _settings()
    snapshot = await evaluate_cost_guard(settings, store, source="graph")
    if snapshot.should_block:
        return {
            "error": "cost_kill_switch_active",
            "agent_message": "MAESTRO pausado pelo cost monitor.",
            "cost_guard": snapshot.model_dump(),
            "done": True,
        }
    return {"cost_guard": snapshot.model_dump()}


async def triage_node(state: dict[str, Any]) -> dict[str, Any]:
    """Classify input and decide which agent should handle it."""
    input_data = state.get("input_data", {})
    input_type = state.get("input_type", "")

    # If target_agent is already set (e.g. cron jobs or direct invocation), respect it
    forced_target = state.get("target_agent")
    if forced_target:
        return {
            "triage_result": {
                "business": state.get("business", "roberts"),
                "target_agent": forced_target,
                "confidence": 1.0,
                "intent": "forced_route",
            },
            "target_agent": forced_target,
        }

    # GHL leads skip triage and go straight to SDR
    if input_type == "ghl_lead":
        business = state.get("business", "roberts")
        return {
            "triage_result": {
                "business": business,
                "target_agent": "sdr",
                "confidence": 1.0,
                "intent": "inbound_lead",
            },
            "target_agent": "sdr",
        }

    # Telegram messages go through triage
    text = input_data.get("text", "")
    last_business = input_data.get("last_business", "roberts")
    result = await triage_message(text, last_business)

    return {
        "triage_result": result,
        "target_agent": result.get("target_agent"),
    }


async def sdr_node(state: dict[str, Any]) -> dict[str, Any]:
    """Run the SDR agent on an inbound lead."""
    input_data = state.get("input_data", {})
    business = state.get("business", "roberts")
    event_id = state.get("event_id", "")

    lead_in = LeadIn(
        event_id=event_id,
        business=business,
        name=input_data.get("name"),
        phone=input_data.get("phone"),
        email=input_data.get("email"),
        source=input_data.get("source", "unknown"),
        message=input_data.get("message") or input_data.get("text"),
        estimated_ticket_usd=input_data.get("estimated_ticket_usd"),
        raw=input_data.get("raw", {}),
    )

    settings = _settings()
    profile = load_profile(business)
    agent = SDRAgent(settings, profile)
    async with trace_agent_run(
        settings,
        name="sdr_run",
        agent="sdr",
        business=business,
        event_id=event_id,
        inputs=lead_in.model_dump(mode="json"),
    ) as trace_run:
        lead, approval, run = await agent.prepare_lead(lead_in)
        trace_run.end(
            {
                "approval_id": approval.id,
                "lead_id": str(lead.id),
                "qualification_score": lead.qualification_score,
                "profit_signal": run.profit_signal,
            }
        )
        run.langsmith_trace_url = trace_run.url

    # Persist to InMemoryStore (same as old MaestroOrchestrator)
    await store.upsert_lead(lead)
    await store.create_approval(approval)
    await store.add_agent_run(run)
    await store.add_audit_log(
        event_type="agent_decision",
        business=lead.business,
        agent="sdr",
        action="approval_requested",
        payload={
            "event_id": lead.event_id,
            "lead_id": str(lead.id),
            "approval_id": approval.id,
            "profit_signal": run.profit_signal,
        },
    )

    return {
        "agent_name": "sdr",
        "agent_message": "SDR lead draft ready for approval.",
        "profit_signal": "conversion",
        "agent_output": {
            "lead_id": str(lead.id),
            "qualification_score": lead.qualification_score,
            "qualification_reasoning": lead.qualification_reasoning,
            "email": approval.preview.get("email"),
            "meeting_slots": approval.preview.get("meeting_slots"),
        },
        "approval": approval.model_dump(mode="json"),
    }


async def prospecting_node(state: dict[str, Any]) -> dict[str, Any]:
    """Run the ProspectingAgent to prepare a batch of outreach emails."""
    business = state.get("business", "roberts")
    input_data = state.get("input_data", {})
    mode = input_data.get("mode", "owned")
    batch_size = input_data.get("batch_size")

    settings = _settings()
    agent = ProspectingAgent(settings, store)
    async with trace_agent_run(
        settings,
        name="prospecting_run",
        agent="prospecting",
        business=business,
        event_id=state.get("event_id"),
        inputs={"mode": mode, "batch_size": batch_size},
    ) as trace_run:
        approval, run = await agent.prepare_roberts_batch(
            batch_size=batch_size, mode=mode
        )
        trace_run.end(
            {
                "approval_id": approval.id if approval else None,
                "profit_signal": run.profit_signal,
                "has_approval": approval is not None,
            }
        )
        run.langsmith_trace_url = trace_run.url

    if approval:
        await store.create_approval(approval)
        await store.add_agent_run(run)
        return {
            "agent_name": "prospecting",
            "agent_message": f"Prospecting batch ready: {approval.preview.get('campaign', {}).get('batch_size', 0)} contacts.",
            "profit_signal": "pipeline",
            "approval": approval.model_dump(mode="json"),
        }

    await store.add_agent_run(run)
    return {
        "agent_name": "prospecting",
        "agent_message": "No prospects in queue.",
        "profit_signal": "pipeline",
        "approval": None,
    }


async def phase1_agent_node(state: dict[str, Any]) -> dict[str, Any]:
    """Run non-SDR Phase 1 agents after triage."""
    input_data = state.get("input_data", {})
    text = input_data.get("text", "")
    business = state.get("triage_result", {}).get("business") or state.get("business", "roberts")
    target_agent = state.get("target_agent") or "operations"

    settings = _settings()
    profile = load_profile(business)

    async with trace_agent_run(
        settings,
        name=f"{target_agent}_run",
        agent=target_agent,
        business=business,
        event_id=state.get("event_id"),
        inputs={"text": text},
    ) as trace_run:
        if target_agent == "marketing":
            agent_result, run = await MarketingAgent(settings, profile).create_post(text)
        elif target_agent == "cfo":
            agent_result, run = await CFOAgent(settings, profile).run(text)
        elif target_agent == "cmo":
            agent_result, run = await CMOAgent(settings, profile).run(text)
        elif target_agent == "ceo":
            agent_result, run = await CEOAgent(settings, profile).run(text)
        else:
            agent_result, run = await OperationsAgent(settings, profile).prepare_task(text)
        trace_run.end(
            {
                "agent_name": agent_result.agent_name,
                "profit_signal": agent_result.profit_signal,
                "has_approval": agent_result.approval is not None,
                "status": agent_result.status,
            }
        )
        run.langsmith_trace_url = trace_run.url

    await store.add_agent_run(run)
    await store.add_audit_log(
        event_type="agent_decision",
        business=business,
        agent=agent_result.agent_name,
        action="agent_completed",
        payload={
            "event_id": state.get("event_id"),
            "profit_signal": agent_result.profit_signal,
            "has_approval": agent_result.approval is not None,
        },
    )

    approval = None
    if agent_result.approval:
        approval = agent_result.approval.model_dump(mode="json")
        await store.create_approval(agent_result.approval)
    else:
        await store.add_business_metric(
            {
                "business": business,
                "metric_type": agent_result.agent_name,
                "metric_data": agent_result.data,
                "generated_by": agent_result.agent_name,
            }
        )

    return {
        "business": business,
        "agent_name": agent_result.agent_name,
        "agent_message": agent_result.message,
        "profit_signal": agent_result.profit_signal,
        "agent_output": agent_result.data,
        "approval": approval,
    }


async def hitl_node(state: dict[str, Any]) -> dict[str, Any]:
    """Pause execution and wait for human approval via Telegram.

    This node calls `interrupt()` which serializes the state to the
    checkpointer (Redis in prod, Memory in tests) and returns control.
    """
    approval = state.get("approval")
    if not approval:
        log.warning("hitl_no_approval", state_keys=list(state.keys()))
        return {"human_decision": True}

    # Send the approval card to Thiago
    settings = _settings()
    telegram = TelegramService(settings)
    approval_id = approval["id"]
    await telegram.send_approval_card(approval_id, approval["preview"])

    # Interrupt — state is saved, execution pauses here
    decision = interrupt({
        "approval_id": approval_id,
        "preview": approval["preview"],
        "question": "Approve this action?",
    })

    log.info("hitl_resumed", approval_id=approval_id, decision=decision)
    return {"human_decision": bool(decision)}


async def execute_node(state: dict[str, Any]) -> dict[str, Any]:
    """Execute the approved action (or record dry-run)."""
    approval_data = state.get("approval")
    human_decision = state.get("human_decision")

    if not human_decision or not approval_data:
        return {
            "execution_result": {"status": "skipped", "reason": "not_approved"},
        }

    # Reconstruct ApprovalRequest from serialized dict
    approval = ApprovalRequest(**approval_data)
    executor = DryRunActionExecutor(store)
    result = await executor.execute_approval(approval)

    return {"execution_result": result}


async def finalize_node(state: dict[str, Any]) -> dict[str, Any]:
    """Record final state to InMemoryStore and mark event processed."""
    # For now, just mark as done. The webhooks handle processed_events
    # and audit_log separately to maintain compatibility.
    return {"done": True}
