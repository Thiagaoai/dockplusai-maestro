from datetime import UTC, datetime

from maestro.services.call_targets import build_call_targets


def test_build_call_targets_prioritizes_engaged_contacts():
    send_rows = [
        {
            "created_at": "2026-04-26T12:00:00+00:00",
            "payload": {
                "sent": [
                    {"source_ref": "ref-1", "email": "one@example.com", "email_id": "email-1"},
                    {"source_ref": "ref-2", "email": "two@example.com", "email_id": "email-2"},
                    {"source_ref": "ref-3", "email": "three@example.com", "email_id": "email-3"},
                ]
            },
        }
    ]
    event_rows = [
        {
            "created_at": "2026-04-26T12:02:00+00:00",
            "payload": {"normalized": {"email_id": "email-1", "event_type": "email.delivered"}},
        },
        {
            "created_at": "2026-04-26T12:03:00+00:00",
            "payload": {"normalized": {"email_id": "email-2", "event_type": "email.opened"}},
        },
        {
            "created_at": "2026-04-26T12:04:00+00:00",
            "payload": {"normalized": {"email_id": "email-3", "event_type": "email.bounced"}},
        },
    ]
    leads = {
        "ref-1": {"name": "One", "phone": "111", "email": "one@example.com"},
        "ref-2": {"name": "Two", "phone": "222", "email": "two@example.com"},
        "ref-3": {"name": "Three", "phone": "333", "email": "three@example.com"},
    }

    targets = build_call_targets(send_rows, event_rows, leads)

    assert [target.email for target in targets] == [
        "two@example.com",
        "one@example.com",
        "three@example.com",
    ]
    assert targets[0].priority == "high"
    assert targets[0].status == "opened"
    assert targets[1].priority == "call"
    assert targets[1].status == "delivered"
    assert targets[2].priority == "blocked"
    assert targets[2].status == "do_not_call"
    assert targets[0].last_event_at == datetime(2026, 4, 26, 12, 3, tzinfo=UTC)
