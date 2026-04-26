import pytest

from maestro.config import Settings
from maestro.repositories import store
from maestro.schemas.events import ApprovalRequest, LeadRecord
from maestro.services.actions import DryRunActionExecutor
from maestro.services.prospecting import prospect_queue_item


class FakeEmail:
    async def send_business_email(self, **kwargs):
        if kwargs["to"] == "fail@example.com":
            from maestro.services.resend import ResendError

            raise ResendError("resend failed")
        return {"status": "sent", "email_id": f"email_{kwargs['to']}", "cc": kwargs.get("cc") or []}


@pytest.mark.asyncio
async def test_real_web_prospecting_records_verified_sent_and_failed_counts():
    sent_lead = LeadRecord(
        event_id="scrape:ok",
        business="roberts",
        name="Verified Property",
        email="ok@example.com",
        source="scrape",
        raw={"source_url": "https://example.com/ok", "verification": "verified"},
    )
    failed_lead = LeadRecord(
        event_id="scrape:fail",
        business="roberts",
        name="Failed Property",
        email="fail@example.com",
        source="scrape",
        raw={"source_url": "https://example.com/fail", "verification": "verified"},
    )
    await store.upsert_lead(sent_lead)
    await store.upsert_lead(failed_lead)

    ok_item = prospect_queue_item("roberts", sent_lead, "verified_web", "scrape:ok", "scrape")
    fail_item = prospect_queue_item("roberts", failed_lead, "verified_web", "scrape:fail", "scrape")
    await store.upsert_prospect_queue_item(ok_item)
    await store.upsert_prospect_queue_item(fail_item)

    approval = ApprovalRequest(
        business="roberts",
        event_id="approval:web",
        action="prospecting_batch_send_html",
        preview={
            "campaign": {"flow": "roberts web"},
            "email": {"subject": "Offer", "text": "Body", "html": "<p>Body</p>", "cc": ["cc@example.com"]},
            "prospects": [
                {
                    "source_type": "scrape",
                    "source_name": "verified_web",
                    "source_ref": "scrape:ok",
                    "lead_id": str(sent_lead.id),
                    "property_name": "Verified Property",
                },
                {
                    "source_type": "scrape",
                    "source_name": "verified_web",
                    "source_ref": "scrape:fail",
                    "lead_id": str(failed_lead.id),
                    "property_name": "Failed Property",
                },
            ],
            "force_real_send": True,
            "dry_run": False,
        },
    )

    result = await DryRunActionExecutor(
        store,
        settings=Settings(dry_run=True, resend_api_key="test-key"),
        email=FakeEmail(),
    ).execute_approval(approval)

    assert result["attempted_count"] == 2
    assert result["sent_count"] == 1
    assert result["failed_count"] == 1
    assert store.clients_web_verified[0]["property_name"] == "Verified Property"
    assert store.clients_web_verified[0]["email"] == "ok@example.com"
    statuses = {item["source_ref"]: item["status"] for item in store.prospect_queue}
    assert statuses == {"scrape:ok": "sent", "scrape:fail": "failed"}
