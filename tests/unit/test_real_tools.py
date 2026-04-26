import pytest

from maestro.agents.cfo import CFOAgent
from maestro.agents.cmo import CMOAgent
from maestro.config import Settings
from maestro.profiles import load_profile
from maestro.repositories.store import InMemoryStore
from maestro.schemas.events import ApprovalRequest
from maestro.services.actions import DryRunActionExecutor
from maestro.services.postforme import PostformeClient


class FakePostforme:
    def __init__(self) -> None:
        self.calls = []

    async def publish_or_schedule(self, **kwargs):
        self.calls.append(kwargs)
        return {"status": "scheduled", "post_id": "post_1", "platform": kwargs["platform"]}


@pytest.mark.asyncio
async def test_postforme_skips_without_credentials():
    result = await PostformeClient(
        Settings(postforme_api_key="", postforme_account_roberts_instagram="")
    ).publish_or_schedule(
        business="roberts",
        caption="Test",
        image_url="https://example.com/image.jpg",
    )

    assert result["status"] == "skipped"
    assert result["reason"] == "missing_postforme_api_key"


@pytest.mark.asyncio
async def test_marketing_approval_executes_postforme_when_not_dry_run():
    store = InMemoryStore()
    fake_postforme = FakePostforme()
    approval = ApprovalRequest(
        business="roberts",
        event_id="marketing:test",
        action="marketing_publish_or_schedule_post",
        preview={
            "caption": "Spring cleanup season",
            "hashtags": ["#CapeCod", "#Landscaping"],
            "image_url": "https://example.com/image.jpg",
            "platform": "instagram",
            "scheduled_at": "2026-04-27T09:00:00-04:00",
        },
    )

    result = await DryRunActionExecutor(
        store,
        settings=Settings(dry_run=False),
        postforme=fake_postforme,
    ).execute_approval(approval)

    assert result["tool"] == "postforme"
    assert result["status"] == "scheduled"
    assert fake_postforme.calls[0]["caption"].startswith("Spring cleanup season")
    assert store.audit_log[-1].action == "marketing_publish_or_schedule_post"


@pytest.mark.asyncio
async def test_operations_calendar_skips_without_start_time():
    store = InMemoryStore()
    approval = ApprovalRequest(
        business="roberts",
        event_id="operations:test",
        action="operations_external_action_dry_run",
        preview={"prepared": {"kind": "calendar", "summary": "Call Alice"}},
    )

    result = await DryRunActionExecutor(
        store,
        settings=Settings(dry_run=False),
    ).execute_approval(approval)

    assert result["status"] == "skipped"
    assert result["result"]["reason"] == "missing_calendar_start"


@pytest.mark.asyncio
async def test_cfo_uses_stripe_summary_when_available(monkeypatch):
    async def fake_summary(self, business, limit=100):
        return {
            "status": "ok",
            "charges_checked": 3,
            "succeeded_count": 2,
            "gross_revenue_usd": 1200.0,
            "refunded_usd": 50.0,
            "sources": ["stripe"],
        }

    monkeypatch.setattr("maestro.services.stripe.StripeClient.recent_charges_summary", fake_summary)

    result, _run = await CFOAgent(Settings(), load_profile("roberts")).run("finance")

    assert result.data["reconciliation"]["stripe_charges_checked"] == 3
    assert "stripe" in result.data["reconciliation"]["sources"]


@pytest.mark.asyncio
async def test_cmo_uses_real_marketing_sources_when_available(monkeypatch):
    async def fake_meta(self, business):
        return {"status": "ok", "spend_usd": 100.0, "clicks": 20, "impressions": 1000, "sources": ["meta_ads"]}

    async def fake_google(self, business):
        return {"status": "ok", "spend_usd": 50.0, "clicks": 10, "impressions": 500, "sources": ["google_ads"]}

    async def fake_gbp(self):
        return {"status": "ok", "account_count": 1, "sources": ["gbp"]}

    monkeypatch.setattr("maestro.services.marketing_channels.MetaAdsClient.account_insights", fake_meta)
    monkeypatch.setattr("maestro.services.marketing_channels.GoogleAdsClient.customer_insights", fake_google)
    monkeypatch.setattr("maestro.services.marketing_channels.GBPClient.account_status", fake_gbp)

    result, _run = await CMOAgent(Settings(), load_profile("roberts")).run("ads")

    assert result.data["performance"]["real_spend_usd_last_30d"] == 150.0
    assert result.data["performance"]["real_clicks_last_30d"] == 30
    assert set(result.data["performance"]["sources"]) == {"meta_ads", "google_ads", "gbp"}
