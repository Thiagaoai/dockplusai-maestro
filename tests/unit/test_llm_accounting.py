from types import SimpleNamespace

import pytest

from maestro.config import Settings
from maestro.schemas.events import AgentRunRecord
from maestro.utils.langsmith import trace_agent_run
from maestro.utils.llm import (
    HAIKU,
    OPUS,
    SONNET,
    UnknownModelPricingError,
    call_claude,
    call_claude_json,
    calculate_cost_usd,
    collect_llm_usage,
    usage_from_response,
)


class _FakeMessages:
    def __init__(self, text: str, input_tokens: int = 1000, output_tokens: int = 2000) -> None:
        self.text = text
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens

    async def create(self, **kwargs):
        return SimpleNamespace(
            content=[SimpleNamespace(text=self.text)],
            usage=SimpleNamespace(
                input_tokens=self.input_tokens,
                output_tokens=self.output_tokens,
            ),
        )


class _FakeClient:
    def __init__(self, text: str, input_tokens: int = 1000, output_tokens: int = 2000) -> None:
        self.messages = _FakeMessages(text, input_tokens, output_tokens)


def test_calculates_cost_by_model_family():
    assert calculate_cost_usd(OPUS, tokens_in=1_000_000, tokens_out=1_000_000) == 90.0
    assert calculate_cost_usd(SONNET, tokens_in=1_000_000, tokens_out=1_000_000) == 18.0
    assert calculate_cost_usd(HAIKU, tokens_in=1_000_000, tokens_out=1_000_000) == 4.8


def test_parses_usage_from_anthropic_response_objects_and_dicts():
    object_response = SimpleNamespace(usage=SimpleNamespace(input_tokens=12, output_tokens=34))
    dict_response = SimpleNamespace(usage={"input_tokens": 56, "output_tokens": 78})

    assert usage_from_response(object_response) == (12, 34)
    assert usage_from_response(dict_response) == (56, 78)


@pytest.mark.asyncio
async def test_call_claude_records_usage_and_cost(monkeypatch):
    import maestro.utils.llm as llm

    monkeypatch.setattr(llm, "get_client", lambda settings: _FakeClient("hello", 1000, 2000))
    settings = Settings(app_env="test", anthropic_api_key="test")

    with collect_llm_usage() as usage:
        text = await call_claude("system", "user", settings=settings, model=SONNET)

    assert text == "hello"
    assert usage.tokens_in == 1000
    assert usage.tokens_out == 2000
    assert usage.cost_usd == 0.033


@pytest.mark.asyncio
async def test_call_claude_json_remains_compatible(monkeypatch):
    import maestro.utils.llm as llm

    monkeypatch.setattr(llm, "get_client", lambda settings: _FakeClient('{"ok": true}', 10, 20))
    settings = Settings(app_env="test", anthropic_api_key="test")

    result = await call_claude_json("system", "user", settings=settings, model=HAIKU)

    assert result == {"ok": True}


@pytest.mark.asyncio
async def test_unknown_model_pricing_fails_in_production():
    settings = Settings(app_env="production", anthropic_api_key="test")

    with pytest.raises(UnknownModelPricingError):
        await call_claude("system", "user", settings=settings, model="claude-mystery")


@pytest.mark.asyncio
async def test_trace_agent_run_applies_usage_to_agent_run(monkeypatch):
    import maestro.utils.llm as llm

    monkeypatch.setattr(llm, "get_client", lambda settings: _FakeClient("hello", 100, 50))
    settings = Settings(app_env="test", anthropic_api_key="test", langsmith_tracing=False)
    run = AgentRunRecord(
        business="roberts",
        agent_name="cfo",
        input="in",
        output="out",
        profit_signal="margin",
        prompt_version="v1",
    )

    async with trace_agent_run(
        settings,
        name="cfo_run",
        agent="cfo",
        business="roberts",
        event_id="evt-1",
        inputs={"question": "test"},
    ) as trace:
        await call_claude("system", "user", settings=settings, model=SONNET)
        trace.end({"ok": True})
        trace.apply_to_run(run)

    assert run.tokens_in == 100
    assert run.tokens_out == 50
    assert run.cost_usd == 0.00105
