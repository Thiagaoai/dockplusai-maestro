from datetime import UTC, datetime

import pytest

from maestro.config import Settings
from maestro.repositories import store
from maestro.schemas.events import AgentRunRecord
from maestro.services import cost_monitor


@pytest.mark.asyncio
async def test_cost_monitor_triggers_kill_switch(monkeypatch):
    monkeypatch.setattr(cost_monitor, "set_stopped", lambda: None)
    store.agent_runs.append(
        AgentRunRecord(
            business="roberts",
            agent_name="cfo",
            input="in",
            output="out",
            profit_signal="margin",
            prompt_version="v1",
            cost_usd=31.0,
            created_at=datetime.now(UTC),
        )
    )
    settings = Settings(
        app_env="test",
        daily_cost_alert_usd=15.0,
        daily_cost_kill_usd=30.0,
        monthly_cost_kill_usd=500.0,
    )

    snapshot = await cost_monitor.evaluate_cost_guard(settings, store, source="test")

    assert snapshot.status == "killed"
    assert snapshot.reason == "daily_cost_kill_usd"
    assert store.paused is True
    assert store.audit_log[0].action == "cost_kill_switch_triggered"


@pytest.mark.asyncio
async def test_cost_monitor_alert_does_not_pause(monkeypatch):
    monkeypatch.setattr(cost_monitor, "set_stopped", lambda: None)
    store.agent_runs.append(
        AgentRunRecord(
            business="roberts",
            agent_name="cmo",
            input="in",
            output="out",
            profit_signal="roas",
            prompt_version="v1",
            cost_usd=16.0,
            created_at=datetime.now(UTC),
        )
    )
    settings = Settings(
        app_env="test",
        daily_cost_alert_usd=15.0,
        daily_cost_kill_usd=30.0,
        monthly_cost_kill_usd=500.0,
    )

    snapshot = await cost_monitor.evaluate_cost_guard(settings, store, source="test")

    assert snapshot.status == "alert"
    assert store.paused is False
    assert store.audit_log[0].action == "cost_alert_threshold_crossed"
