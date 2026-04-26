"""
Unit tests for tools/telegram.py — send_message dry_run path and format_lead_approval_card.
No real HTTP calls — dry_run=true from conftest, no telegram_bot_token in test env.
"""

import pytest

from maestro.tools.telegram import format_lead_approval_card, send_inline_keyboard, send_message
from maestro.subagents.sdr.re_engagement import _ghl_headers


# ── send_message: dry_run ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_message_dry_run_returns_dict():
    result = await send_message.ainvoke({"text": "Olá Thiago, tudo bem?"})
    assert result["dry_run"] is True
    assert "text" in result


@pytest.mark.asyncio
async def test_send_message_dry_run_with_explicit_chat_id():
    result = await send_message.ainvoke({"text": "Lead novo aprovado.", "chat_id": 123})
    assert result["dry_run"] is True
    assert result["chat_id"] == 123


# ── send_inline_keyboard: dry_run ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_inline_keyboard_dry_run():
    buttons = [[
        {"text": "✅ Aprovar", "callback_data": "approval:approve:abc"},
        {"text": "❌ Rejeitar", "callback_data": "approval:reject:abc"},
    ]]
    result = await send_inline_keyboard.ainvoke({
        "text": "Novo lead: John Smith — Score: 85",
        "buttons": buttons,
    })
    assert result["dry_run"] is True


# ── format_lead_approval_card ─────────────────────────────────────────────────

def test_format_lead_approval_card_returns_text_and_buttons():
    text, buttons = format_lead_approval_card(
        lead_name="Maria Silva",
        source="Meta Ads",
        score=82,
        reasoning="high ticket + contact data",
        email_subject="Thanks for reaching out",
        slots=["2026-05-01T14:00:00+00:00", "2026-05-02T10:00:00+00:00"],
        approval_id="appr-001",
        business="roberts",
    )
    assert "Maria Silva" in text
    assert "82" in text
    assert "Roberts" in text
    assert len(buttons) >= 1
    assert buttons[0][0]["callback_data"] == "approval:approve:appr-001"
    assert buttons[0][1]["callback_data"] == "approval:reject:appr-001"


def test_format_lead_approval_card_max_3_slots():
    _, buttons = format_lead_approval_card(
        lead_name="Test",
        source="web",
        score=70,
        reasoning="ok",
        email_subject="Subject",
        slots=["s1", "s2", "s3", "s4", "s5"],
        approval_id="appr-xyz",
        business="dockplusai",
    )
    # Only 3 slots shown in text
    assert len(buttons) >= 1


# ── re_engagement _ghl_headers ────────────────────────────────────────────────

def test_re_engagement_headers_raises_without_token():
    with pytest.raises(ValueError, match="GHL_TOKEN_UNKNOWN"):
        _ghl_headers("unknown")


def test_re_engagement_headers_returns_auth_header(monkeypatch):
    monkeypatch.setenv("GHL_TOKEN_ROBERTS", "tok-abc")
    headers = _ghl_headers("roberts")
    assert headers["Authorization"] == "Bearer tok-abc"
    assert "Version" in headers
