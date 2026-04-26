from typing import Any

from maestro.agents.ceo import CEOAgent
from maestro.agents.cfo import CFOAgent
from maestro.agents.cmo import CMOAgent
from maestro.agents.marketing import MarketingAgent
from maestro.agents.operations import OperationsAgent
from maestro.agents.sdr import SDRAgent
from maestro.agents.triage import triage_message
from maestro.config import Settings
from maestro.profiles import load_profile
from maestro.schemas.events import AgentResult, LeadIn
from maestro.services.telegram import TelegramService


class MaestroOrchestrator:
    """Vertical-slice orchestrator.

    This is deliberately deterministic for the first implementation. LangGraph can
    replace this shell once Redis checkpointing and interrupt() are wired.
    """

    def __init__(self, settings: Settings, store) -> None:
        self.settings = settings
        self.store = store
        self.telegram = TelegramService(settings)

    async def handle_inbound_lead(self, lead_in: LeadIn) -> dict[str, Any]:
        if self.store.paused:
            await self.store.add_audit_log(
                event_type="agent_decision",
                business=lead_in.business,
                agent="sdr",
                action="skipped_paused",
                payload={"event_id": lead_in.event_id},
            )
            return {"status": "paused", "event_id": lead_in.event_id}

        if await self.store.is_processed(lead_in.event_id):
            return {
                "status": "duplicate",
                "event_id": lead_in.event_id,
                "result": await self.store.get_processed_result(lead_in.event_id),
            }

        profile = load_profile(lead_in.business)
        agent = SDRAgent(self.settings, profile)
        lead, approval, run = await agent.prepare_lead(lead_in)

        await self.store.upsert_lead(lead)
        await self.store.create_approval(approval)
        await self.store.add_agent_run(run)
        await self.store.add_audit_log(
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
        telegram_result = await self.telegram.send_approval_card(approval.id, approval.preview)
        result = {
            "status": "approval_requested",
            "event_id": lead.event_id,
            "lead_id": str(lead.id),
            "approval_id": approval.id,
            "telegram": telegram_result,
            "dry_run": self.settings.dry_run,
        }
        await self.store.mark_processed(
            lead.event_id,
            source="ghl",
            business=lead.business,
            result=result,
        )
        return result

    async def handle_text_message(self, text: str, default_business: str = "roberts") -> dict[str, Any]:
        if self.store.paused:
            await self.store.add_audit_log(
                event_type="agent_decision",
                business=default_business,
                agent="triage",
                action="skipped_paused",
                payload={"text": text[:120]},
            )
            return {"status": "paused"}

        route = await triage_message(text, last_business=default_business)
        business = str(route["business"])
        profile = load_profile(business)
        target_agent = str(route["target_agent"])

        if target_agent == "marketing":
            agent_result, run = await MarketingAgent(self.settings, profile).create_post(text)
        elif target_agent == "cfo":
            agent_result, run = await CFOAgent(self.settings, profile).run(text)
        elif target_agent == "cmo":
            agent_result, run = await CMOAgent(self.settings, profile).run(text)
        elif target_agent == "ceo":
            agent_result, run = await CEOAgent(self.settings, profile).run(text)
        elif target_agent == "sdr":
            lead = LeadIn(
                event_id=f"telegram-lead:{business}:{abs(hash(text))}",
                business=business,
                source="telegram",
                message=text,
            )
            lead_record, approval, run = await SDRAgent(self.settings, profile).prepare_lead(lead)
            await self.store.upsert_lead(lead_record)
            agent_result = AgentResult(
                business=business,
                agent_name="sdr",
                message="SDR lead draft ready for approval.",
                data=approval.preview,
                approval=approval,
                profit_signal="conversion",
            )
        else:
            agent_result, run = await OperationsAgent(self.settings, profile).prepare_task(text)

        await self.store.add_agent_run(run)
        await self.store.add_audit_log(
            event_type="agent_decision",
            business=business,
            agent=agent_result.agent_name,
            action="agent_completed",
            payload={
                "target_agent": target_agent,
                "profit_signal": agent_result.profit_signal,
                "has_approval": agent_result.approval is not None,
            },
        )
        telegram_result: dict[str, Any]
        if agent_result.approval:
            await self.store.create_approval(agent_result.approval)
            telegram_result = await self.telegram.send_approval_card(
                agent_result.approval.id,
                agent_result.approval.preview,
            )
            status_value = "approval_requested"
        else:
            telegram_result = await self.telegram.send_message(agent_result.message)
            status_value = "completed"
            await self.store.add_business_metric(
                {
                    "business": business,
                    "metric_type": agent_result.agent_name,
                    "metric_data": agent_result.data,
                    "generated_by": agent_result.agent_name,
                }
            )

        return {
            "status": status_value,
            "route": route,
            "agent": agent_result.agent_name,
            "business": business,
            "message": agent_result.message,
            "approval_id": agent_result.approval.id if agent_result.approval else None,
            "telegram": telegram_result,
            "profit_signal": agent_result.profit_signal,
        }
