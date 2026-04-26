from maestro.repositories import store
from maestro.schemas.events import LeadRecord
from maestro.services.prospecting import prospect_queue_item


def telegram_message(client, text: str, update_id: int = 300):
    return client.post(
        "/webhooks/telegram",
        json={"update_id": update_id, "message": {"chat": {"id": 123}, "text": text}},
        headers={"x-telegram-bot-api-secret-token": "telegram-test-secret"},
    )


def seed_prospect(name: str, email: str, source_type: str, source_ref: str):
    lead = LeadRecord(
        event_id=source_ref,
        business="roberts",
        name=name,
        email=email,
        source=source_type,
        status="prospect_imported",
    )
    store.leads[str(lead.id)] = lead
    item = prospect_queue_item(
        business="roberts",
        lead=lead,
        source_name="test",
        source_ref=source_ref,
        source_type=source_type,
    )
    store.prospect_queue.append(item)
    return lead, item


def test_prospect_roberts_command_creates_batch_approval(client):
    seed_prospect("Owned One", "owned1@example.com", "customer_file", "owned-1")
    seed_prospect("Owned Two", "owned2@example.com", "customer_file", "owned-2")
    seed_prospect("Scrape One", "scrape1@example.com", "scrape", "scrape-1")

    response = telegram_message(client, "prospect roberts 3", 301)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "approval_requested"
    assert data["agent"] == "prospecting"
    approval = store.approvals[data["approval_id"]]
    assert approval.action == "prospecting_batch_send_html"
    assert approval.preview["campaign"]["batch_size"] == 3
    assert [p["source_type"] for p in approval.preview["prospects"]] == [
        "customer_file",
        "customer_file",
        "scrape",
    ]
    assert all(item["status"] == "drafted" for item in store.prospect_queue)


def test_prospecting_batch_approval_executes_dry_run(client):
    seed_prospect("Owned One", "owned1@example.com", "customer_file", "owned-1")
    response = telegram_message(client, "prospect roberts 1", 302)
    approval_id = response.json()["approval_id"]

    callback = {
        "update_id": 303,
        "callback_query": {
            "id": "callback-prospecting-1",
            "data": f"approval:approve:{approval_id}",
            "message": {"chat": {"id": 123}},
        },
    }
    approved = client.post(
        "/webhooks/telegram",
        json=callback,
        headers={"x-telegram-bot-api-secret-token": "telegram-test-secret"},
    )

    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert len(store.dry_run_actions) == 1
    assert store.dry_run_actions[0]["action"] == "prospecting_batch_send_html"
