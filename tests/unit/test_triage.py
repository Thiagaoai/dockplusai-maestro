from types import SimpleNamespace

import pytest

from maestro.agents.triage import triage_message
from maestro.config import get_settings


class FakeMessages:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(content=[SimpleNamespace(text=self.content)])


class FakeAnthropicClient:
    def __init__(self, content: str) -> None:
        self.messages = FakeMessages(content)


@pytest.mark.asyncio
async def test_triage_uses_keyword_fallback_without_api_key():
    result = await triage_message("Create an Instagram caption for Roberts", "roberts")

    assert result["business"] == "roberts"
    assert result["target_agent"] == "marketing"
    assert result["function"] == "marketing"


@pytest.mark.asyncio
async def test_triage_uses_claude_haiku_when_api_key_is_configured(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    monkeypatch.setenv("ANTHROPIC_TRIAGE_MODEL", "claude-haiku-4-5-test")
    get_settings.cache_clear()
    client = FakeAnthropicClient(
        '{"business":"<last_active>","function":"finance","intent":"review invoices",'
        '"confidence":0.91,"target_agent":"cfo"}'
    )

    result = await triage_message("Can you review this invoice situation?", "dockplusai", client)

    assert result == {
        "business": "dockplusai",
        "function": "finance",
        "intent": "review invoices",
        "confidence": 0.91,
        "target_agent": "cfo",
    }
    assert client.messages.calls[0]["model"] == "claude-haiku-4-5-test"
    assert client.messages.calls[0]["temperature"] == 0


@pytest.mark.asyncio
async def test_triage_normalizes_llm_aliases(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    get_settings.cache_clear()
    client = FakeAnthropicClient(
        '{"business":"roberts","function":"marketing_performance","intent":"review ads",'
        '"confidence":0.87,"target_agent":"cmo_agent"}'
    )

    result = await triage_message("How are Google Ads doing?", "roberts", client)

    assert result["function"] == "marketing"
    assert result["target_agent"] == "cmo"


@pytest.mark.asyncio
async def test_triage_falls_back_when_llm_response_is_invalid(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    get_settings.cache_clear()
    client = FakeAnthropicClient("not json")

    result = await triage_message("Need a weekly briefing", "roberts", client)

    assert result["business"] == "roberts"
    assert result["target_agent"] == "ceo"
