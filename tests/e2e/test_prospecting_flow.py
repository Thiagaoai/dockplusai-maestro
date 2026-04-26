from maestro.repositories import store
from maestro.schemas.events import LeadRecord
from maestro.services.prospecting import prospect_queue_item
from maestro.services.tavily import WebProspect


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
    assert approval.preview["campaign"]["batch_size"] == 2
    assert approval.preview["campaign"]["flow"] == "roberts 10"
    assert [p["source_type"] for p in approval.preview["prospects"]] == [
        "customer_file",
        "customer_file",
    ]
    assert [item["status"] for item in store.prospect_queue] == ["drafted", "drafted", "queued"]


def test_prospect_roberts_web_uses_scrape_queue_only(client):
    seed_prospect("Owned One", "owned1@example.com", "customer_file", "owned-1")
    seed_prospect("Scrape One", "scrape1@example.com", "scrape", "scrape-1")

    response = telegram_message(client, "prospect roberts web", 304)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "approval_requested"
    assert data["mode"] == "web"
    approval = store.approvals[data["approval_id"]]
    assert approval.preview["campaign"]["flow"] == "roberts web"
    assert [p["source_type"] for p in approval.preview["prospects"]] == ["scrape"]


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


def test_prospect_web_hoa_searches_tavily_and_creates_real_send_approval(client, monkeypatch):
    async def fake_search(self, target, locations, max_results_per_location=5):
        return [
            WebProspect(
                name="Harbor HOA",
                email="manager@harborhoa.org",
                source_url="https://harborhoa.example/contact",
                source_title="Harbor HOA Contact",
                verification_note="Official contact page lists this email.",
                location=locations[0],
                target=target,
                raw={"title": "Harbor HOA Contact", "url": "https://harborhoa.example/contact"},
            )
        ]

    monkeypatch.setattr(
        "maestro.services.tavily.TavilyProspectFinder.search_prospects",
        fake_search,
    )

    response = telegram_message(client, "prospect web hoa", 305)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "approval_requested"
    assert data["target"] == "hoa"
    approval = store.approvals[data["approval_id"]]
    assert approval.preview["campaign"]["target"] == "hoa"
    assert approval.preview["campaign"]["locations"] == [
        "Cape Cod",
        "South Shore",
        "Martha's Vineyard",
        "Nantucket",
    ]
    assert approval.preview["dry_run"] is False
    assert approval.preview["force_real_send"] is True
    assert approval.preview["prospects"][0]["source_url"] == "https://harborhoa.example/contact"


def test_prospect_web_then_target_continues_pending_flow(client, monkeypatch):
    async def fake_search(self, target, locations, max_results_per_location=5):
        return [
            WebProspect(
                name="Island Condo Association",
                email="board@islandcondo.org",
                source_url="https://islandcondo.example/contact",
                source_title="Island Condo Contact",
                verification_note="Official contact page lists this email.",
                location=locations[-1],
                target=target,
                raw={"title": "Island Condo Contact", "url": "https://islandcondo.example/contact"},
            )
        ]

    monkeypatch.setattr(
        "maestro.services.tavily.TavilyProspectFinder.search_prospects",
        fake_search,
    )

    first = telegram_message(client, "prospect web", 306)
    assert first.status_code == 200
    assert first.json()["status"] == "needs_target"
    assert store.telegram_pending_commands[123]["command"] == "prospect_web"

    second = telegram_message(client, "hoa", 307)

    assert second.status_code == 200
    data = second.json()
    assert data["status"] == "approval_requested"
    assert data["target"] == "hoa"
    assert 123 not in store.telegram_pending_commands
    approval = store.approvals[data["approval_id"]]
    assert approval.preview["prospects"][0]["property_name"] == "Island Condo Association"
