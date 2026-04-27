from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class IntentType(StrEnum):
    admin = "admin"
    status = "status"
    workflow = "workflow"
    approval = "approval"
    help = "help"
    unknown = "unknown"
    legacy = "legacy"


class CommandIntent(BaseModel):
    intent_type: IntentType
    action: str
    raw_text: str
    business: str | None = None
    agent: str | None = None
    subagent: str | None = None
    workflow: str | None = None
    entities: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    missing_fields: list[str] = Field(default_factory=list)
    requires_confirmation: bool = False


class InlineButton(BaseModel):
    text: str
    callback_data: str


class TelegramReply(BaseModel):
    text: str
    buttons: list[list[InlineButton]] = Field(default_factory=list)
    parse_mode: str = "Markdown"
    followup: bool = False

    def payload(self, chat_id: int) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": self.text,
            "parse_mode": self.parse_mode,
        }
        if self.buttons:
            payload["reply_markup"] = {
                "inline_keyboard": [
                    [button.model_dump() for button in row]
                    for row in self.buttons
                ]
            }
        return payload

