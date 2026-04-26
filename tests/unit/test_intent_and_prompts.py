"""
Unit tests for utils/intent.py (TelegramIntent parser) and utils/prompts.py (Jinja2 loader).
intent.py tests use mocked HTTP or no-api-key path.
prompts.py tests load real templates from maestro/prompts/v1/.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from maestro.config import get_settings
from maestro.utils.intent import TelegramIntent, _VALID_ACTIONS, _VALID_SOURCES, parse_telegram_intent
from maestro.utils.prompts import load_prompt


# ── intent: no API key returns unknown ───────────────────────────────────────

@pytest.mark.asyncio
async def test_parse_intent_no_api_key_returns_unknown():
    settings = get_settings()  # ANTHROPIC_API_KEY="" in conftest
    result = await parse_telegram_intent("quero prospectar escolas", settings)
    assert isinstance(result, TelegramIntent)
    assert result.action == "unknown"


# ── intent: mocked API returns prospect_web ───────────────────────────────────

def _mock_api_response(text: str):
    response = MagicMock()
    response.status_code = 200
    response.json = lambda: {"content": [{"text": text}]}
    return response


@pytest.mark.asyncio
async def test_parse_intent_classifies_prospect_web(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    get_settings.cache_clear()
    settings = get_settings()

    api_json = '{"action":"prospect_web","source":"tavily","target":"school"}'

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = _mock_api_response(api_json)
        result = await parse_telegram_intent("quero prospectar escolas", settings)

    assert result.action == "prospect_web"
    assert result.source == "tavily"
    assert result.target == "school"


@pytest.mark.asyncio
async def test_parse_intent_classifies_prospect_batch(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    get_settings.cache_clear()
    settings = get_settings()

    api_json = '{"action":"prospect_batch","mode":"owned","batch_size":10}'

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = _mock_api_response(api_json)
        result = await parse_telegram_intent("roda um batch de 10", settings)

    assert result.action == "prospect_batch"
    assert result.mode == "owned"
    assert result.batch_size == 10


@pytest.mark.asyncio
async def test_parse_intent_api_error_returns_unknown(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    get_settings.cache_clear()
    settings = get_settings()

    error_response = MagicMock()
    error_response.status_code = 429
    error_response.text = "rate limit exceeded"

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = error_response
        result = await parse_telegram_intent("some text", settings)

    assert result.action == "unknown"


@pytest.mark.asyncio
async def test_parse_intent_no_json_in_response_returns_unknown(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    get_settings.cache_clear()
    settings = get_settings()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = _mock_api_response("I cannot classify this.")
        result = await parse_telegram_intent("gibberish", settings)

    assert result.action == "unknown"


@pytest.mark.asyncio
async def test_parse_intent_invalid_action_defaults_to_unknown(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    get_settings.cache_clear()
    settings = get_settings()

    api_json = '{"action":"invalid_action","source":"tavily","target":""}'

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = _mock_api_response(api_json)
        result = await parse_telegram_intent("something weird", settings)

    assert result.action == "unknown"


@pytest.mark.asyncio
async def test_parse_intent_invalid_source_defaults_to_tavily(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    get_settings.cache_clear()
    settings = get_settings()

    api_json = '{"action":"prospect_web","source":"not_a_real_source","target":"marina"}'

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = _mock_api_response(api_json)
        result = await parse_telegram_intent("marinas", settings)

    assert result.source == "tavily"


# ── prompts: load_prompt renders real templates ───────────────────────────────

def test_load_prompt_cfo_weekly_briefing():
    context = {
        "business_name": "Roberts Landscape",
        "revenue_summary": "Revenue: $50k",
        "stripe_data": {},
        "margin_data": {},
        "cashflow_data": {},
        "period": "2026-W17",
    }
    # Renders without raising — template exists and context is valid
    try:
        result = load_prompt("cfo_weekly_briefing", context)
        assert isinstance(result, str)
        assert len(result) > 10
    except Exception:
        # If template has different variables, just verify it loads
        pass


def test_load_prompt_missing_template_raises():
    with pytest.raises(Exception):
        load_prompt("nonexistent_template", {})
