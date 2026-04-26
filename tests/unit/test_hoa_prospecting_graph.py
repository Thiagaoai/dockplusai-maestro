import pytest

from maestro.agents.hoa_prospecting_graph import build_provincetown_hoa_graph
from maestro.repositories import store


@pytest.mark.anyio
async def test_provincetown_hoa_graph_seeds_verified_contacts_without_sending():
    graph = build_provincetown_hoa_graph()

    result = await graph.ainvoke(
        {
            "business": "roberts",
            "campaign": "provincetown_hoa_web",
            "cc": ["thiago@example.com"],
            "dry_run": True,
        }
    )

    assert len(result["prepared"]) == 10
    assert len(result["sent"]) == 10
    assert {item["status"] for item in result["sent"]} == {"dry_run"}
    assert len(store.leads) == 10
    assert len(store.prospect_queue) == 10
    assert {item["source_name"] for item in store.prospect_queue} == {
        "provincetown_hoa_verified_web"
    }
    assert store.audit_log[-1].action == "provincetown_hoa_email_batch"
    assert store.audit_log[-1].payload["dry_run"] is True
