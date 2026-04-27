from __future__ import annotations

from typing import Any

from maestro.config import Settings
from maestro.repositories import store
from maestro.services.telegram import TelegramService
from maestro.telegram.parser import parse_command
from maestro.telegram.router import TelegramCommandRouter
from maestro.telegram.session import get_last_context, set_last_context


class TelegramCommandService:
    def __init__(self, settings: Settings, telegram: TelegramService | None = None) -> None:
        self.settings = settings
        self.telegram = telegram or TelegramService(settings)

    async def handle_message(self, *, text: str, chat_id: int, update_id: str) -> dict:
        context = get_last_context(chat_id)
        last_business = context.get("last_business", "roberts")
        intent = await parse_command(text, self.settings, last_business=last_business)
        result, reply = await TelegramCommandRouter(self.settings, store, self.telegram).route(
            intent,
            update_id=update_id,
        )
        if intent.business:
            set_last_context(chat_id, {"last_business": intent.business, "last_agent": intent.agent})
        if reply is not None:
            await self.telegram.send_reply(reply)
        return {
            **result,
            "intent": intent.model_dump(mode="json"),
            "route": "telegram_cockpit",
        }

