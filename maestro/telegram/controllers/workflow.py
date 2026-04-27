from __future__ import annotations

import json
from typing import Any

from maestro.agents.ceo import CEOAgent
from maestro.agents.cfo import CFOAgent
from maestro.agents.cmo import CMOAgent
from maestro.agents.marketing import MarketingAgent
from maestro.agents.operations import OperationsAgent
from maestro.agents.prospecting import ProspectingAgent
from maestro.config import Settings
from maestro.profiles import load_profile
from maestro.schemas.events import AgentResult, AgentRunRecord, ApprovalRequest, LeadIn
from maestro.services.telegram import TelegramService
from maestro.telegram.schemas import CommandIntent
from maestro.utils.langsmith import trace_agent_run


class WorkflowController:
    def __init__(self, settings: Settings, store: Any, telegram: TelegramService) -> None:
        self.settings = settings
        self.store = store
        self.telegram = telegram

    async def handle(self, intent: CommandIntent) -> dict:
        if intent.action == "run_prospecting_batch":
            return await self._prospecting_batch(intent)
        if intent.action == "run_web_prospecting":
            return await self._web_prospecting(intent)
        if intent.action == "create_marketing_post":
            return await self._marketing_post(intent)
        if intent.action == "run_cfo_briefing":
            return await self._phase1_agent(intent, "cfo")
        if intent.action == "run_cmo_review":
            return await self._phase1_agent(intent, "cmo")
        if intent.action == "run_ceo_briefing":
            return await self._phase1_agent(intent, "ceo")
        if intent.action == "prepare_operations_task":
            return await self._phase1_agent(intent, "operations")
        if intent.action == "process_sdr_lead":
            return await self._sdr_text(intent)
        return {"status": "ignored", "reason": "unsupported_workflow", "workflow": intent.workflow}

    async def _prospecting_batch(self, intent: CommandIntent) -> dict:
        business = intent.business or "roberts"
        if business != "roberts":
            return {"status": "unsupported", "agent": "prospecting", "business": business}
        batch_size = intent.entities.get("batch_size") or self.settings.prospecting_batch_size_roberts
        mode = intent.entities.get("mode") or "owned"
        async with trace_agent_run(
            self.settings,
            name="telegram_prospecting_batch",
            agent="prospecting",
            business=business,
            event_id="telegram:prospecting_batch",
            inputs={"batch_size": batch_size, "mode": mode},
        ) as trace_run:
            approval, run = await ProspectingAgent(self.settings, self.store).prepare_roberts_batch(
                int(batch_size),
                mode=mode,
            )
            trace_run.end({"approval_id": approval.id if approval else None, "has_approval": approval is not None})
            trace_run.apply_to_run(run)
        await self.store.add_agent_run(run)
        if approval:
            await self._persist_approval("prospecting", approval, {"batch_size": len(approval.preview.get("prospects", []))})
            await self.telegram.send_approval_card(approval.id, approval.preview)
            return {
                "status": "approval_requested",
                "agent": "prospecting",
                "business": business,
                "approval_id": approval.id,
                "batch_size": len(approval.preview.get("prospects", [])),
                "mode": mode,
            }
        return {"status": "empty", "agent": "prospecting", "business": business, "mode": mode}

    async def _web_prospecting(self, intent: CommandIntent) -> dict:
        business = intent.business or "roberts"
        target = intent.entities.get("target")
        source = intent.entities.get("source") or "tavily"
        if not target:
            return {
                "status": "needs_target",
                "agent": "prospecting",
                "business": business,
                "source": source,
                "message": "Qual target voce quer prospectar? Exemplo: hoa",
            }
        async with trace_agent_run(
            self.settings,
            name="telegram_prospecting_web_search",
            agent="prospecting",
            business=business,
            event_id=f"telegram:prospecting_web:{target}",
            inputs={"target": target, "source": source},
        ) as trace_run:
            approval, run = await ProspectingAgent(self.settings, self.store).prepare_roberts_web_search_batch(
                target,
                source=source,
            )
            trace_run.end({"approval_id": approval.id if approval else None, "has_approval": approval is not None})
            trace_run.apply_to_run(run)
        await self.store.add_agent_run(run)
        if approval:
            await self._persist_approval("prospecting", approval, {"target": target, "source": source})
            await self.telegram.send_approval_card(approval.id, approval.preview)
            return {
                "status": "approval_requested",
                "agent": "prospecting",
                "business": business,
                "approval_id": approval.id,
                "batch_size": len(approval.preview.get("prospects", [])),
                "mode": "web",
                "source": source,
                "target": target,
            }
        output = _agent_run_output(run)
        if output.get("status") == "error":
            await self.telegram.send_message(f"Falha na busca web [{source}].\nTarget: {target}\nErro: {output.get('error')}")
            return {"status": "error", "agent": "prospecting", "business": business, "source": source, "target": target}
        await self.telegram.send_message(f"Nao encontrei contatos com email para '{target}' [{source}].")
        return {"status": "empty", "agent": "prospecting", "business": business, "source": source, "target": target}

    async def _marketing_post(self, intent: CommandIntent) -> dict:
        business = intent.business or "roberts"
        topic = intent.entities.get("topic")
        if not topic:
            return {"status": "needs_topic", "agent": "marketing", "business": business}
        profile = load_profile(business)
        async with trace_agent_run(
            self.settings,
            name="telegram_marketing_create_post",
            agent="marketing",
            business=business,
            event_id=f"telegram:marketing:{business}:{topic}",
            inputs={"topic": topic},
        ) as trace_run:
            result, run = await MarketingAgent(self.settings, profile).create_post(topic)
            trace_run.end(_trace_result(result))
            trace_run.apply_to_run(run)
        await self.store.add_agent_run(run)
        if result.approval:
            await self._persist_approval("marketing", result.approval, {"topic": topic})
            await self.telegram.send_approval_card(result.approval.id, result.approval.preview)
            return {
                "status": "approval_requested",
                "agent": "marketing",
                "business": business,
                "approval_id": result.approval.id,
                "topic": topic,
                "profit_signal": result.profit_signal,
            }
        return {"status": "draft_ready", "agent": "marketing", "business": business, "topic": topic}

    async def _phase1_agent(self, intent: CommandIntent, agent_name: str) -> dict:
        business = intent.business or "roberts"
        text = intent.entities.get("text") or intent.raw_text
        profile = load_profile(business)
        async with trace_agent_run(
            self.settings,
            name=f"telegram_{agent_name}",
            agent=agent_name,
            business=business,
            event_id=f"telegram:{agent_name}:{hash(text)}",
            inputs={"text": text},
        ) as trace_run:
            if agent_name == "cfo":
                result, run = await CFOAgent(self.settings, profile).run(text)
            elif agent_name == "cmo":
                result, run = await CMOAgent(self.settings, profile).run(text)
            elif agent_name == "ceo":
                result, run = await CEOAgent(self.settings, profile).run(text)
            else:
                result, run = await OperationsAgent(self.settings, profile).prepare_task(text)
            trace_run.end(_trace_result(result))
            trace_run.apply_to_run(run)
        await self.store.add_agent_run(run)
        await self.store.add_audit_log(
            event_type="agent_decision",
            business=business,
            agent=result.agent_name,
            action="agent_completed",
            payload={"profit_signal": result.profit_signal, "has_approval": result.approval is not None},
        )
        if result.approval:
            await self._persist_approval(result.agent_name, result.approval, {"profit_signal": result.profit_signal})
            await self.telegram.send_approval_card(result.approval.id, result.approval.preview)
            return {
                "status": "approval_requested",
                "agent": result.agent_name,
                "business": business,
                "approval_id": result.approval.id,
                "profit_signal": result.profit_signal,
                "message": result.message,
            }
        await self.store.add_business_metric(
            {
                "business": business,
                "metric_type": result.agent_name,
                "metric_data": result.data,
                "generated_by": result.agent_name,
            }
        )
        return {
            "status": "completed",
            "agent": result.agent_name,
            "business": business,
            "profit_signal": result.profit_signal,
            "message": result.message,
        }

    async def _sdr_text(self, intent: CommandIntent) -> dict:
        from maestro.graph import MaestroGraph

        business = intent.business or "roberts"
        lead_text = intent.entities.get("lead_text") or intent.raw_text
        lead_in = LeadIn(
            event_id=f"telegram:sdr:{hash(lead_text)}",
            business=business,
            name=None,
            source="telegram",
            message=lead_text,
            raw={"telegram_text": lead_text},
        )
        return await MaestroGraph(self.settings, self.store).handle_inbound_lead(lead_in)

    async def _persist_approval(self, agent: str, approval: ApprovalRequest, payload: dict[str, Any]) -> None:
        await self.store.create_approval(approval)
        await self.store.add_audit_log(
            event_type="agent_decision",
            business=approval.business,
            agent=agent,
            action="approval_requested",
            payload={"approval_id": approval.id, **payload},
        )


def _trace_result(result: AgentResult) -> dict[str, Any]:
    return {
        "agent_name": result.agent_name,
        "profit_signal": result.profit_signal,
        "has_approval": result.approval is not None,
        "status": result.status,
    }


def _agent_run_output(run: AgentRunRecord) -> dict:
    try:
        return json.loads(run.output)
    except (TypeError, json.JSONDecodeError):
        return {}

