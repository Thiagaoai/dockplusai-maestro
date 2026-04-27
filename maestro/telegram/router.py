from __future__ import annotations

from typing import Any

from maestro.config import Settings
from maestro.repositories.store import InMemoryStore
from maestro.services.telegram import TelegramService
from maestro.telegram.controllers.admin import AdminController
from maestro.telegram.controllers.approval import ApprovalController
from maestro.telegram.controllers.status import StatusController
from maestro.telegram.controllers.workflow import WorkflowController
from maestro.telegram.guards import guard_workflow
from maestro.telegram.renderers import (
    agents_reply,
    clarification_reply,
    costs_reply,
    errors_reply,
    help_reply,
    pending_reply,
    simple_reply,
    status_reply,
)
from maestro.telegram.schemas import CommandIntent, IntentType, TelegramReply


class TelegramCommandRouter:
    def __init__(self, settings: Settings, store: Any, telegram: TelegramService) -> None:
        self.settings = settings
        self.store = store
        self.telegram = telegram

    async def route(self, intent: CommandIntent, *, update_id: str = "") -> tuple[dict, TelegramReply | None]:
        if intent.intent_type == IntentType.legacy:
            return {"status": "legacy"}, None
        if intent.intent_type == IntentType.help:
            return {"status": "help"}, help_reply()
        if intent.intent_type == IntentType.admin:
            result = await AdminController(self.store).handle(intent, update_id=update_id)
            return result, simple_reply(result.get("message", result["status"]))
        if intent.intent_type == IntentType.status:
            return await self._status(intent)
        if intent.intent_type == IntentType.approval:
            approvals = await ApprovalController(self.store).list_pending()
            return {"status": "ok", "approvals": approvals}, pending_reply(approvals)
        if intent.intent_type == IntentType.workflow:
            if intent.missing_fields:
                return await self._missing_fields(intent)
            guard = await guard_workflow(self.settings, self.store, intent)
            if guard:
                return {"status": "blocked", "reason": guard.text}, guard
            result = await WorkflowController(self.settings, self.store, self.telegram).handle(intent)
            return result, self._workflow_reply(result)
        return {"status": "unknown"}, help_reply()

    async def _status(self, intent: CommandIntent) -> tuple[dict, TelegramReply]:
        controller = StatusController(self.settings, self.store)
        if intent.action == "system_status":
            data = await controller.system_status()
            return {"status": "ok", "system": data}, status_reply(data)
        if intent.action == "cost_status":
            data = await controller.cost_status()
            return {"status": "ok", "costs": data}, costs_reply(data)
        if intent.action == "agent_status":
            data = await controller.agents()
            return {"status": "ok", **data}, agents_reply(data["agents"], data["paused"])
        if intent.action == "recent_errors":
            errors = await controller.recent_errors()
            return {"status": "ok", "errors": errors}, errors_reply(errors)
        data = await controller.system_status()
        return {"status": "ok", "system": data}, status_reply(data)

    async def _missing_fields(self, intent: CommandIntent) -> tuple[dict, TelegramReply]:
        field = intent.missing_fields[0]
        if field == "target":
            reply = clarification_reply("Qual target voce quer prospectar? Exemplo: hoa")
        elif field == "topic":
            reply = clarification_reply("Qual o tema do post? Exemplo: spring cleanup")
        else:
            reply = clarification_reply(f"Falta informar: {field}")
        return {
            "status": f"needs_{field}",
            "agent": intent.agent,
            "business": intent.business,
            "source": intent.entities.get("source"),
        }, reply

    def _workflow_reply(self, result: dict) -> TelegramReply | None:
        status = result.get("status")
        if status == "approval_requested":
            return None
        if status == "completed":
            return simple_reply(str(result.get("message") or "Fluxo concluido."))
        if status and status.startswith("needs_"):
            return simple_reply(str(result.get("message") or "Preciso de mais informacao."))
        if status == "empty":
            return None
        if status == "error":
            return simple_reply(f"Falha no fluxo {result.get('agent')}: {result.get('error', 'erro desconhecido')}")
        return simple_reply(str(result.get("message") or result.get("status") or "OK"))

