from types import SimpleNamespace

import pytest

from maestro.config import get_settings
from maestro.graph_nodes import phase1_agent_node
from maestro.repositories import store


class _FakeMessages:
    async def create(self, **kwargs):
        return SimpleNamespace(
            content=[SimpleNamespace(text='{"summary":"LLM CFO summary","recommended_actions":["Watch margin"]}')],
            usage=SimpleNamespace(input_tokens=1200, output_tokens=300),
        )


class _FakeClient:
    messages = _FakeMessages()


@pytest.mark.asyncio
async def test_mocked_anthropic_agent_run_persists_tokens_and_cost(monkeypatch):
    import maestro.utils.llm as llm

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    get_settings.cache_clear()
    monkeypatch.setattr(llm, "get_client", lambda settings: _FakeClient())

    await phase1_agent_node(
        {
            "business": "roberts",
            "event_id": "test:cfo:llm-accounting",
            "input_type": "telegram_message",
            "input_data": {"text": "weekly financial briefing"},
            "target_agent": "cfo",
            "triage_result": {"business": "roberts"},
        }
    )

    assert len(store.agent_runs) == 1
    run = store.agent_runs[0]
    assert run.agent_name == "cfo"
    assert run.tokens_in == 1200
    assert run.tokens_out == 300
    assert run.cost_usd == 0.0081
