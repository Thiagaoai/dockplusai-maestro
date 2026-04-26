from types import SimpleNamespace

import pytest

from maestro.config import Settings
from maestro.repositories.supabase_store import SupabaseStore
from maestro.schemas.events import AgentRunRecord, ApprovalRequest, ApprovalStatus, LeadRecord


class FakeQuery:
    def __init__(self, client, table_name: str):
        self.client = client
        self.table_name = table_name
        self._operation = "select"
        self._payload = None
        self._on_conflict = None
        self._filters = []
        self._limit = None
        self._orders = []

    def select(self, *_args):
        self._operation = "select"
        return self

    def insert(self, payload):
        self._operation = "insert"
        self._payload = payload
        return self

    def upsert(self, payload, **kwargs):
        self._operation = "upsert"
        self._payload = payload
        self._on_conflict = kwargs.get("on_conflict")
        return self

    def update(self, payload):
        self._operation = "update"
        self._payload = payload
        return self

    def eq(self, key, value):
        self._filters.append((key, value))
        return self

    def limit(self, value):
        self._limit = value
        return self

    def order(self, key, desc=False):
        self._orders.append((key, desc))
        return self

    def execute(self):
        rows = self.client.tables.setdefault(self.table_name, [])
        if self._operation == "insert":
            rows.append(dict(self._payload))
            return SimpleNamespace(data=[self._payload])
        if self._operation == "upsert":
            payload = dict(self._payload)
            keys = [key.strip() for key in self._on_conflict.split(",")] if self._on_conflict else []
            if not keys:
                keys = ["id" if "id" in payload else "event_id"]
            for idx, row in enumerate(rows):
                if all(row.get(key) == payload.get(key) for key in keys):
                    rows[idx] = payload
                    break
            else:
                rows.append(payload)
            return SimpleNamespace(data=[payload])
        if self._operation == "update":
            selected = self._select_rows(rows)
            for row in selected:
                row.update(self._payload)
            return SimpleNamespace(data=selected)
        return SimpleNamespace(data=self._select_rows(rows))

    def _select_rows(self, rows):
        selected = list(rows)
        for key, value in self._filters:
            selected = [row for row in selected if row.get(key) == value]
        for key, desc in reversed(self._orders):
            selected = sorted(selected, key=lambda row: row.get(key) or 0, reverse=desc)
        if self._limit is not None:
            selected = selected[: self._limit]
        return selected


class FakeSupabaseClient:
    def __init__(self):
        self.tables = {}

    def table(self, table_name: str):
        return FakeQuery(self, table_name)


class FailingSupabaseClient(FakeSupabaseClient):
    def table(self, table_name: str):
        if table_name in {"approval_threads", "dry_run_actions"}:
            raise RuntimeError(f"missing table {table_name}")
        return super().table(table_name)


@pytest.fixture
def supabase_store():
    settings = Settings(
        storage_backend="supabase",
        supabase_url="https://example.supabase.co",
        supabase_service_key="service-key",
    )
    return SupabaseStore(settings, client=FakeSupabaseClient())


@pytest.fixture
def supabase_store_missing_runtime_tables():
    settings = Settings(
        storage_backend="supabase",
        supabase_url="https://example.supabase.co",
        supabase_service_key="service-key",
    )
    return SupabaseStore(settings, client=FailingSupabaseClient())


@pytest.mark.asyncio
async def test_supabase_store_processed_events_round_trip(supabase_store):
    assert await supabase_store.is_processed("evt-1") is False

    await supabase_store.mark_processed("evt-1", "ghl", {"ok": True}, business="roberts")

    assert await supabase_store.is_processed("evt-1") is True
    assert await supabase_store.get_processed_result("evt-1") == {"ok": True}


@pytest.mark.asyncio
async def test_supabase_store_core_records_round_trip(supabase_store):
    lead = LeadRecord(event_id="lead-1", business="roberts", name="Maria")
    await supabase_store.upsert_lead(lead)
    assert (await supabase_store.get_lead(str(lead.id))).name == "Maria"

    run = AgentRunRecord(
        business="roberts",
        agent_name="sdr",
        input="in",
        output="out",
        profit_signal="conversion",
        prompt_version="v1",
    )
    await supabase_store.add_agent_run(run)
    assert supabase_store.client.tables["agent_runs"][0]["profit_signal"] == "conversion"

    metric = {"business": "roberts", "metric_type": "cfo", "metric_data": {"margin": 42}}
    await supabase_store.add_business_metric(metric)
    assert supabase_store.client.tables["business_metrics"][0]["metric_data"] == {"margin": 42}


@pytest.mark.asyncio
async def test_supabase_store_approval_and_audit(supabase_store):
    approval = ApprovalRequest(
        business="roberts",
        event_id="approval-1",
        action="marketing_publish_or_schedule_post",
        preview={"topic": "patio"},
    )
    await supabase_store.create_approval(approval)
    stored = await supabase_store.get_approval(approval.id)
    assert stored.status == ApprovalStatus.pending

    decided = await supabase_store.decide_approval(approval.id, approved=True)
    assert decided.status == ApprovalStatus.approved
    assert supabase_store.client.tables["approval_requests"][0]["status"] == "approved"

    audit = await supabase_store.add_audit_log(
        event_type="human_approval",
        action="approved",
        payload={"approval_id": approval.id},
        business="roberts",
        agent="marketing",
    )
    assert audit.hash
    assert supabase_store.client.tables["audit_log"][0]["hash"] == audit.hash


@pytest.mark.asyncio
async def test_supabase_store_maps_approval_threads(supabase_store):
    approval = ApprovalRequest(
        business="roberts",
        event_id="approval-thread-1",
        action="sdr_dry_run_follow_up",
        preview={"lead": "Alice"},
    )
    await supabase_store.create_approval(approval)

    await supabase_store.map_approval_to_thread(approval.id, "thread-123")

    assert await supabase_store.get_thread_for_approval(approval.id) == "thread-123"
    assert supabase_store.client.tables["approval_threads"][0]["approval_id"] == approval.id


@pytest.mark.asyncio
async def test_supabase_store_records_dry_run_actions(supabase_store):
    action = {
        "action": "sdr_dry_run_follow_up",
        "approval_id": "approval-1",
        "business": "roberts",
        "dry_run": True,
    }

    await supabase_store.record_dry_run_action(action)

    rows = supabase_store.client.tables["dry_run_actions"]
    assert rows[0]["approval_id"] == "approval-1"
    assert rows[0]["payload"] == action


@pytest.mark.asyncio
async def test_supabase_store_runtime_tables_fail_open(supabase_store_missing_runtime_tables):
    await supabase_store_missing_runtime_tables.map_approval_to_thread("approval-1", "thread-1")
    assert await supabase_store_missing_runtime_tables.get_thread_for_approval("approval-1") is None

    action = {"action": "dry_run", "approval_id": "approval-1", "business": "roberts"}
    assert await supabase_store_missing_runtime_tables.record_dry_run_action(action) == action


@pytest.mark.asyncio
async def test_supabase_store_upserts_clients_web_verified(supabase_store):
    item = {
        "business": "roberts",
        "property_name": "Race Point Townhouse Condominiums",
        "email": "racepointcondos@example.com",
        "source_name": "provincetown_hoa_verified_web",
        "campaign": "roberts web",
        "email_id": "email_1",
        "payload": {"source": "verified"},
    }

    await supabase_store.upsert_clients_web_verified(item)
    await supabase_store.upsert_clients_web_verified({**item, "email_id": "email_2"})

    rows = supabase_store.client.tables["clients_web_verified"]
    assert len(rows) == 1
    assert rows[0]["email_id"] == "email_2"
