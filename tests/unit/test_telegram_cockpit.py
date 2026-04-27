import pytest

from maestro.config import Settings
from maestro.telegram.parser import parse_command
from maestro.telegram.registry import AGENT_REGISTRY
from maestro.telegram.schemas import IntentType


@pytest.mark.asyncio
async def test_parser_routes_admin_status_and_workflows_without_llm():
    settings = Settings(app_env="test", anthropic_api_key="")

    status = await parse_command("/status", settings)
    assert status.intent_type == IntentType.status
    assert status.action == "system_status"

    pause = await parse_command("pausa marketing", settings)
    assert pause.intent_type == IntentType.admin
    assert pause.action == "pause_agent"
    assert pause.agent == "marketing"

    cfo = await parse_command("CFO Roberts agora", settings)
    assert cfo.intent_type == IntentType.workflow
    assert cfo.agent == "cfo"
    assert cfo.business == "roberts"

    post = await parse_command("faz post DockPlus sobre AI automation ROI", settings)
    assert post.agent == "marketing"
    assert post.business == "dockplusai"
    assert post.entities["topic"] == "ai automation roi"


def test_registry_covers_agents_and_subagents_from_cockpit_sdd():
    expected = {
        "sdr",
        "prospecting",
        "marketing",
        "cfo",
        "cmo",
        "ceo",
        "operations",
        "brand_guardian",
    }

    assert expected.issubset(set(AGENT_REGISTRY))
    assert "lead_qualifier" in AGENT_REGISTRY["sdr"].subagents
    assert "caption_writer" in AGENT_REGISTRY["marketing"].subagents
    assert "calendar_manager" in AGENT_REGISTRY["operations"].subagents
