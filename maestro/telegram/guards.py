from __future__ import annotations

from maestro.config import Settings
from maestro.memory.redis_session import is_stopped
from typing import Any
from maestro.services.cost_monitor import evaluate_cost_guard
from maestro.telegram.control_state import is_paused
from maestro.telegram.schemas import CommandIntent, TelegramReply


async def guard_workflow(settings: Settings, store: Any, intent: CommandIntent) -> TelegramReply | None:
    if store.paused or is_stopped():
        return TelegramReply(text="MAESTRO esta pausado. Envie /start para retomar.")
    if intent.business and is_paused("business", intent.business):
        return TelegramReply(text=f"{intent.business} esta pausado.")
    if intent.agent and is_paused("agent", intent.agent):
        return TelegramReply(text=f"{intent.agent} esta pausado.")
    snapshot = await evaluate_cost_guard(settings, store, source="telegram")
    if snapshot.should_block:
        return TelegramReply(text="MAESTRO pausado pelo cost monitor. Revise custos antes de retomar.")
    return None
