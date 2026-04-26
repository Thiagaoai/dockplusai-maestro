"""
Unit tests for the Resend email tool.
Uses httpx mocking for successful sends; tests no-key path directly.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from maestro.tools.resend_email import send_email, send_email_html


# ── no API key raises ValueError ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_email_raises_without_api_key():
    with pytest.raises(ValueError, match="RESEND_API_KEY not set"):
        await send_email.ainvoke({
            "to": "lead@example.com",
            "subject": "Your estimate",
            "body": "Hi there",
            "from_address": "team@robertslandscapecod.com",
        })


@pytest.mark.asyncio
async def test_send_email_html_raises_without_api_key():
    with pytest.raises(ValueError, match="RESEND_API_KEY not set"):
        await send_email_html.ainvoke({
            "to": "lead@example.com",
            "subject": "Your estimate",
            "html_body": "<p>Hi</p>",
            "text_body": "Hi",
            "from_address": "team@robertslandscapecod.com",
        })


# ── successful send with mocked HTTP ─────────────────────────────────────────

def _mock_response(json_data: dict):
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = lambda: json_data
    return response


@pytest.mark.asyncio
async def test_send_email_returns_email_id(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "test-resend-key")
    from maestro.config import get_settings
    get_settings.cache_clear()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = _mock_response({"id": "re_abc123"})

        result = await send_email.ainvoke({
            "to": "lead@example.com",
            "subject": "Thanks for reaching out",
            "body": "Hi Sarah, ...",
            "from_address": "team@robertslandscapecod.com",
        })

    assert result["email_id"] == "re_abc123"
    assert result["to"] == "lead@example.com"
    assert result["subject"] == "Thanks for reaching out"


@pytest.mark.asyncio
async def test_send_email_includes_idempotency_header(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "test-resend-key")
    from maestro.config import get_settings
    get_settings.cache_clear()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = _mock_response({"id": "re_idem"})

        await send_email.ainvoke({
            "to": "lead@example.com",
            "subject": "Test",
            "body": "Body",
            "from_address": "team@robertslandscapecod.com",
            "idempotency_key": "key-123",
        })

    called_headers = mock_post.call_args.kwargs.get("headers", {})
    assert called_headers.get("Idempotency-Key") == "key-123"


@pytest.mark.asyncio
async def test_send_email_html_returns_email_id(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "test-resend-key")
    from maestro.config import get_settings
    get_settings.cache_clear()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = _mock_response({"id": "re_html456"})

        result = await send_email_html.ainvoke({
            "to": "lead@example.com",
            "subject": "Follow-up",
            "html_body": "<p>Hi Sarah</p>",
            "text_body": "Hi Sarah",
            "from_address": "team@robertslandscapecod.com",
        })

    assert result["email_id"] == "re_html456"
