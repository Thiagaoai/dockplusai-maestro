"""
Telegram tools — LangChain @tool wrappers.

These are the agent-facing tools. The TelegramService in services/telegram.py
is the low-level HTTP client. These wrappers add retry, idempotency,
and structlog so agents can call them like any other tool.

Mobile-first rules (CLAUDE.md):
- Max 5-6 lines of body before buttons
- Bold (*text*) for numbers and names
- Inline keyboard on every actionable message
- One message per event — never split
"""

from typing import Any

import httpx
import structlog
from langchain_core.tools import tool
from tenacity import retry, stop_after_attempt, wait_exponential

from maestro.config import get_settings
from maestro.utils.pii import redact_pii

log = structlog.get_logger()

_TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


def _url(method: str) -> str:
    return _TELEGRAM_API.format(token=get_settings().telegram_bot_token, method=method)


@tool
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
async def send_message(text: str, chat_id: int | None = None) -> dict[str, Any]:
    """
    Envia mensagem de texto para o Thiago via Telegram.

    Args:
        text: Corpo da mensagem. Usar *bold* para números e nomes-chave.
              Máximo 5-6 linhas antes de botões de decisão.
        chat_id: ID do chat. Usa TELEGRAM_THIAGO_CHAT_ID se não informado.
    """
    settings = get_settings()
    target = chat_id or settings.telegram_thiago_chat_id

    log.info("telegram_send_message", chat_id=target, text_preview=redact_pii(text[:80]))

    if settings.dry_run or not settings.telegram_bot_token:
        log.info("telegram_send_message_dry_run")
        return {"dry_run": True, "chat_id": target, "text": text}

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            _url("sendMessage"),
            json={"chat_id": target, "text": text, "parse_mode": "Markdown"},
        )
        response.raise_for_status()

    log.info("telegram_send_message_ok", chat_id=target)
    return response.json()


@tool
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
async def send_inline_keyboard(
    text: str,
    buttons: list[list[dict[str, str]]],
    chat_id: int | None = None,
) -> dict[str, Any]:
    """
    Envia mensagem com inline keyboard para aprovação do Thiago.

    Args:
        text: Corpo da mensagem (máx 5-6 linhas).
        buttons: Grade de botões [[{text, callback_data}, ...], ...].
                 Máx 2 botões por linha. Labels: 3 palavras, verbo primeiro.
        chat_id: ID do chat. Usa TELEGRAM_THIAGO_CHAT_ID se não informado.
    """
    settings = get_settings()
    target = chat_id or settings.telegram_thiago_chat_id

    log.info("telegram_send_inline_keyboard", chat_id=target, button_rows=len(buttons))

    if settings.dry_run or not settings.telegram_bot_token:
        log.info("telegram_send_inline_keyboard_dry_run")
        return {"dry_run": True, "chat_id": target, "text": text, "buttons": buttons}

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            _url("sendMessage"),
            json={
                "chat_id": target,
                "text": text,
                "parse_mode": "Markdown",
                "reply_markup": {"inline_keyboard": buttons},
            },
        )
        response.raise_for_status()

    log.info("telegram_send_inline_keyboard_ok", chat_id=target)
    return response.json()


@tool
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
async def edit_message(
    message_id: int,
    text: str,
    chat_id: int | None = None,
) -> dict[str, Any]:
    """
    Edita uma mensagem existente no Telegram (ex: após aprovação, atualizar status).

    Args:
        message_id: ID da mensagem a editar.
        text: Novo texto.
        chat_id: ID do chat. Usa TELEGRAM_THIAGO_CHAT_ID se não informado.
    """
    settings = get_settings()
    target = chat_id or settings.telegram_thiago_chat_id

    if settings.dry_run or not settings.telegram_bot_token:
        return {"dry_run": True, "message_id": message_id, "text": text}

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            _url("editMessageText"),
            json={
                "chat_id": target,
                "message_id": message_id,
                "text": text,
                "parse_mode": "Markdown",
            },
        )
        response.raise_for_status()

    return response.json()


def format_lead_approval_card(
    lead_name: str,
    source: str,
    score: int,
    reasoning: str,
    email_subject: str,
    slots: list[str],
    approval_id: str,
    business: str,
) -> tuple[str, list[list[dict[str, str]]]]:
    """
    Formata o card de aprovação de lead para o Thiago (mobile-first).

    Returns (text, buttons) prontos para send_inline_keyboard.
    """
    slots_fmt = "\n".join(f"  • {s}" for s in slots[:3])
    text = (
        f"*Lead novo — {business.title()}*\n\n"
        f"*Nome:* {lead_name}\n"
        f"*Fonte:* {source}  •  *Score:* {score}/100\n"
        f"*Motivo:* {reasoning}\n\n"
        f"*Email:* {email_subject}\n"
        f"*Horários sugeridos:*\n{slots_fmt}"
    )
    buttons = [
        [
            {"text": "✅ Aprovar tudo", "callback_data": f"approval:approve:{approval_id}"},
            {"text": "❌ Rejeitar", "callback_data": f"approval:reject:{approval_id}"},
        ],
    ]
    return text, buttons
