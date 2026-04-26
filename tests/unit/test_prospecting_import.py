import pytest

from maestro.repositories import store
from maestro.services.prospecting import import_csv_prospects


@pytest.mark.asyncio
async def test_import_csv_prospects_excludes_do_not_contact_and_dedupes(tmp_path):
    csv_path = tmp_path / "roberts_clients.csv"
    csv_path.write_text(
        "\n".join(
            [
                "Name,Email,Phone,Notes,Value",
                "Good Client,good@example.com,508-555-0100,Patio estimate,$12000",
                "Kim Williams,kim@example.com,508-555-0199,Do not contact,$30000",
                "Good Client Duplicate,good@example.com,508-555-0101,Duplicate,$14000",
                ",,,No usable identity,",
            ]
        ),
        encoding="utf-8",
    )

    result = await import_csv_prospects(csv_path, "roberts", store)

    assert result.rows_seen == 4
    assert result.imported == 1
    assert result.skipped_do_not_contact == 1
    assert result.skipped_duplicates == 1
    assert result.skipped_invalid == 1
    assert len(store.leads) == 1
    lead = next(iter(store.leads.values()))
    assert lead.name == "Good Client"
    assert lead.status == "prospect_imported"
    assert store.audit_log[0].action == "csv_prospects_imported"
