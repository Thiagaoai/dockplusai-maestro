import pytest

from maestro.agents.ceo import CEOAgent
from maestro.agents.cfo import CFOAgent
from maestro.agents.cmo import CMOAgent
from maestro.config import Settings
from maestro.profiles import load_profile


@pytest.mark.asyncio
async def test_cfo_uses_ghl_pipeline_summary_for_cashflow(monkeypatch):
    async def fake_stripe(self, business, limit=100):
        return {"status": "skipped", "reason": "missing", "sources": []}

    async def fake_pipeline(self, business):
        return {
            "status": "ok",
            "open_count": 2,
            "open_value_usd": 40_000.0,
            "won_count": 1,
            "won_value_usd": 20_000.0,
            "sources": ["ghl:pipelines"],
        }

    monkeypatch.setattr("maestro.services.stripe.StripeClient.recent_charges_summary", fake_stripe)
    monkeypatch.setattr("maestro.services.highlevel.HighLevelClient.pipeline_summary", fake_pipeline)

    result, _run = await CFOAgent(Settings(), load_profile("roberts")).run("finance")

    assert result.data["cashflow"]["pipeline_value_usd"] == 40_000.0
    assert result.data["reconciliation"]["open_pipeline_value_usd"] == 40_000.0
    assert any(
        action["category"] == "revenue_conversion"
        for action in result.data["recommended_actions"]["actions"]
    )


@pytest.mark.asyncio
async def test_cmo_calculates_real_performance_signal(monkeypatch):
    async def fake_meta(self, business):
        return {"status": "ok", "spend_usd": 200.0, "clicks": 80, "impressions": 2000, "sources": ["meta_ads"]}

    async def fake_google(self, business):
        return {"status": "skipped", "sources": []}

    async def fake_gbp(self):
        return {"status": "skipped", "sources": []}

    monkeypatch.setattr("maestro.services.marketing_channels.MetaAdsClient.account_insights", fake_meta)
    monkeypatch.setattr("maestro.services.marketing_channels.GoogleAdsClient.customer_insights", fake_google)
    monkeypatch.setattr("maestro.services.marketing_channels.GBPClient.account_status", fake_gbp)

    result, _run = await CMOAgent(Settings(), load_profile("roberts")).run("ads")

    assert result.data["performance"]["performance_signal"] == "improving"
    assert result.data["performance"]["ctr_pct"] == 4.0
    assert result.data["budget"]["recommendation"] == "prepare_test_budget_shift"
    assert isinstance(result.data["creative_tests"][0], dict)


@pytest.mark.asyncio
async def test_ceo_includes_executive_signals(monkeypatch):
    async def fake_stripe(self, business, limit=100):
        return {"status": "skipped", "reason": "missing", "sources": []}

    async def fake_pipeline(self, business):
        return {
            "status": "ok",
            "open_value_usd": 25_000.0,
            "won_count": 0,
            "won_value_usd": 0.0,
            "sources": ["ghl:pipelines"],
        }

    monkeypatch.setattr("maestro.services.stripe.StripeClient.recent_charges_summary", fake_stripe)
    monkeypatch.setattr("maestro.services.highlevel.HighLevelClient.pipeline_summary", fake_pipeline)

    result, _run = await CEOAgent(Settings(), load_profile("roberts")).run("weekly")

    assert result.data["executive_signals"]["open_pipeline_value_usd"] == 25_000.0
    assert result.data["executive_signals"]["margin_signal"] in {"healthy", "watch", "critical"}
    assert result.data["decisions"][0]["estimated_impact_usd"] >= result.data["decisions"][-1]["estimated_impact_usd"]
