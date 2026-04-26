import pytest

from maestro.repositories import store
from maestro.schedulers import weekly


@pytest.fixture(autouse=True)
def cron_locks(monkeypatch):
    released: list[str] = []
    monkeypatch.setattr(weekly, "is_stopped", lambda: False)
    monkeypatch.setattr(weekly, "acquire_cron_lock", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(weekly, "release_cron_lock", lambda job_name: released.append(job_name))
    return released


def test_setup_scheduler_registers_weekly_jobs(monkeypatch):
    monkeypatch.setenv("SCHEDULER_ENABLED", "true")

    scheduler = weekly.setup_scheduler()

    job_ids = {job.id for job in scheduler.get_jobs()}
    assert {"cfo_weekly", "cmo_weekly", "ceo_weekly", "cost_monitor"}.issubset(job_ids)
    assert len([job_id for job_id in job_ids if job_id.startswith("roberts_prospecting_")]) == 4
    assert scheduler.get_job("cfo_weekly").trigger.fields[5].expressions[0].first == 7


@pytest.mark.asyncio
async def test_weekly_crons_manual_trigger_create_outputs(cron_locks):
    await weekly.run_cfo()
    await weekly.run_cmo()
    await weekly.run_ceo()

    metric_types = [metric["metric_type"] for metric in store.business_metrics]
    assert metric_types.count("cfo_weekly") == 2
    assert metric_types.count("cmo_weekly") == 2
    assert metric_types.count("ceo_weekly") == 2
    assert len(store.agent_runs) == 6
    assert {"cfo_weekly", "cmo_weekly", "ceo_weekly"}.issubset(set(cron_locks))
    assert any(record.action == "ceo_weekly_completed" for record in store.audit_log)


@pytest.mark.asyncio
async def test_weekly_cron_respects_stop_switch(monkeypatch):
    monkeypatch.setattr(weekly, "is_stopped", lambda: True)

    await weekly.run_cfo()

    assert store.business_metrics == []
    assert store.agent_runs == []
