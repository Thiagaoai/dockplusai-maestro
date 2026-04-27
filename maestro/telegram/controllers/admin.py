from __future__ import annotations

from typing import Any

from maestro.memory.redis_session import clear_stopped, set_stopped
from maestro.telegram.control_state import set_paused
from maestro.telegram.schemas import CommandIntent


class AdminController:
    def __init__(self, store: Any) -> None:
        self.store = store

    async def handle(self, intent: CommandIntent, *, update_id: str = "") -> dict:
        action = intent.action
        if action == "pause_all":
            self.store.paused = True
            set_stopped()
            await self.store.add_audit_log(
                event_type="config_change",
                action="agents_paused",
                payload={"source": "telegram_cockpit", "update_id": update_id},
            )
            return {"status": "paused", "message": "MAESTRO pausado. Webhooks continuam ativos."}
        if action == "resume_all":
            self.store.paused = False
            clear_stopped()
            await self.store.add_audit_log(
                event_type="config_change",
                action="agents_resumed",
                payload={"source": "telegram_cockpit", "update_id": update_id},
            )
            return {"status": "resumed", "message": "MAESTRO retomado."}
        if action == "pause_agent" and intent.agent:
            set_paused("agent", intent.agent, True)
            await self.store.add_audit_log(
                event_type="config_change",
                agent=intent.agent,
                action="agent_paused",
                payload={"source": "telegram_cockpit", "agent": intent.agent},
            )
            return {"status": "paused", "agent": intent.agent, "message": f"{intent.agent} pausado."}
        if action == "resume_agent" and intent.agent:
            set_paused("agent", intent.agent, False)
            await self.store.add_audit_log(
                event_type="config_change",
                agent=intent.agent,
                action="agent_resumed",
                payload={"source": "telegram_cockpit", "agent": intent.agent},
            )
            return {"status": "resumed", "agent": intent.agent, "message": f"{intent.agent} retomado."}
        if action == "pause_business" and intent.business:
            set_paused("business", intent.business, True)
            await self.store.add_audit_log(
                event_type="config_change",
                business=intent.business,
                action="business_paused",
                payload={"source": "telegram_cockpit", "business": intent.business},
            )
            return {"status": "paused", "business": intent.business, "message": f"{intent.business} pausado."}
        if action == "resume_business" and intent.business:
            set_paused("business", intent.business, False)
            await self.store.add_audit_log(
                event_type="config_change",
                business=intent.business,
                action="business_resumed",
                payload={"source": "telegram_cockpit", "business": intent.business},
            )
            return {"status": "resumed", "business": intent.business, "message": f"{intent.business} retomado."}
        return {"status": "ignored", "reason": "unsupported_admin_action"}

