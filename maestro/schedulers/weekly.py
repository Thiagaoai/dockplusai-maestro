"""
Weekly cron scheduler — CFO, CMO, CEO.

Schedule (UTC):
  Monday 07:00 → CFO Agent
  Monday 08:00 → CMO Agent
  Monday 09:00 → CEO Agent (reads CFO + CMO output, sends Telegram briefing)

IMPORTANT: every job acquires a Redis distributed lock before running.
Without the lock, APScheduler fires per-process — a fast restart or
multi-replica deploy will double-fire CFO/CMO/CEO. See CLAUDE.md gotchas.
"""

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from maestro.agents.ceo import CEOAgent
from maestro.agents.cfo import CFOAgent
from maestro.agents.cmo import CMOAgent
from maestro.agents.prospecting import ProspectingAgent
from maestro.config import get_settings
from maestro.memory.redis_session import acquire_cron_lock, is_stopped, release_cron_lock
from maestro.profiles import load_profile
from maestro.repositories import store
from maestro.schemas.events import AgentResult, AgentRunRecord
from maestro.services.cost_monitor import evaluate_cost_guard
from maestro.services.telegram import TelegramService

log = structlog.get_logger()

WEEKLY_BUSINESSES = ("roberts", "dockplusai")


# ── job runners ───────────────────────────────────────────────────────────────

async def run_cfo() -> None:
    if is_stopped():
        log.info("cron_skipped_stopped", job="cfo_weekly")
        return
    if not acquire_cron_lock("cfo_weekly"):
        return
    try:
        log.info("cron_cfo_weekly_start")
        settings = get_settings()
        telegram = TelegramService(settings)
        for business in WEEKLY_BUSINESSES:
            result, run = await CFOAgent(settings, load_profile(business)).run()
            await _persist_weekly_result(result, run, "cfo_weekly", telegram)
        log.info("cron_cfo_weekly_done")
    except Exception as exc:
        log.error("cron_cfo_weekly_error", error=str(exc))
    finally:
        release_cron_lock("cfo_weekly")


async def run_cmo() -> None:
    if is_stopped():
        log.info("cron_skipped_stopped", job="cmo_weekly")
        return
    if not acquire_cron_lock("cmo_weekly"):
        return
    try:
        log.info("cron_cmo_weekly_start")
        settings = get_settings()
        telegram = TelegramService(settings)
        for business in WEEKLY_BUSINESSES:
            result, run = await CMOAgent(settings, load_profile(business)).run()
            await _persist_weekly_result(result, run, "cmo_weekly", telegram)
        log.info("cron_cmo_weekly_done")
    except Exception as exc:
        log.error("cron_cmo_weekly_error", error=str(exc))
    finally:
        release_cron_lock("cmo_weekly")


async def run_ceo() -> None:
    if is_stopped():
        log.info("cron_skipped_stopped", job="ceo_weekly")
        return
    if not acquire_cron_lock("ceo_weekly"):
        return
    try:
        log.info("cron_ceo_weekly_start")
        settings = get_settings()
        telegram = TelegramService(settings)
        for business in WEEKLY_BUSINESSES:
            result, run = await CEOAgent(settings, load_profile(business)).run()
            await _persist_weekly_result(result, run, "ceo_weekly", telegram)
            await telegram.send_message(_weekly_briefing_message(result))
        log.info("cron_ceo_weekly_done")
    except Exception as exc:
        log.error("cron_ceo_weekly_error", error=str(exc))
    finally:
        release_cron_lock("ceo_weekly")


async def _persist_weekly_result(
    result: AgentResult,
    run: AgentRunRecord,
    metric_type: str,
    telegram: TelegramService,
) -> None:
    await store.add_agent_run(run)
    await store.add_business_metric(
        {
            "business": result.business,
            "metric_type": metric_type,
            "metric_data": result.data,
            "generated_by": result.agent_name,
        }
    )
    await store.add_audit_log(
        event_type="agent_decision",
        business=result.business,
        agent=result.agent_name,
        action=f"{metric_type}_completed",
        payload={
            "profit_signal": result.profit_signal,
            "has_approval": result.approval is not None,
        },
    )
    if result.approval:
        await store.create_approval(result.approval)
        await store.add_audit_log(
            event_type="agent_decision",
            business=result.business,
            agent=result.agent_name,
            action="approval_requested",
            payload={"approval_id": result.approval.id, "metric_type": metric_type},
        )
        await telegram.send_approval_card(result.approval.id, result.approval.preview)


def _weekly_briefing_message(result: AgentResult) -> str:
    briefing = str(result.data.get("briefing") or result.message or "")
    return (
        f"Weekly CEO briefing - {result.business}\n\n"
        f"{briefing[:1200]}"
    ).strip()


# ── cost monitor ──────────────────────────────────────────────────────────────

async def run_cost_monitor() -> None:
    """Hourly: check daily spend, send alert or trigger kill switch."""
    if not acquire_cron_lock("cost_monitor", timeout=50):
        return
    try:
        settings = get_settings()
        snapshot = await evaluate_cost_guard(settings, store, source="cron")
        log.info("cron_cost_monitor_run", **snapshot.model_dump())
    except Exception as exc:
        log.error("cron_cost_monitor_error", error=str(exc))
    finally:
        release_cron_lock("cost_monitor")


async def run_roberts_prospecting_batch() -> None:
    if is_stopped():
        log.info("cron_skipped_stopped", job="roberts_prospecting_batch")
        return
    if not acquire_cron_lock("roberts_prospecting_batch", timeout=50):
        return
    try:
        settings = get_settings()
        log.info("cron_roberts_prospecting_batch_start")
        approval, run = await ProspectingAgent(settings, store).prepare_roberts_batch(mode="owned")
        await store.add_agent_run(run)
        if not approval:
            log.info("cron_roberts_prospecting_batch_empty")
            return
        await store.create_approval(approval)
        await store.add_audit_log(
            event_type="agent_decision",
            business="roberts",
            agent="prospecting",
            action="approval_requested",
            payload={"approval_id": approval.id, "batch_size": len(approval.preview.get("prospects", []))},
        )
        await TelegramService(settings).send_approval_card(approval.id, approval.preview)
        log.info("cron_roberts_prospecting_batch_approval_sent", approval_id=approval.id)
    except Exception as exc:
        log.error("cron_roberts_prospecting_batch_error", error=str(exc))
    finally:
        release_cron_lock("roberts_prospecting_batch")


# ── scheduler setup ───────────────────────────────────────────────────────────

def setup_scheduler() -> AsyncIOScheduler:
    """Wire all cron jobs. Call once at app startup."""
    settings = get_settings()
    scheduler = AsyncIOScheduler(
        timezone=settings.weekly_scheduler_timezone,
        job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 300},
    )

    # Weekly jobs
    scheduler.add_job(
        run_cfo,
        CronTrigger(
            day_of_week=settings.weekly_cfo_day_of_week,
            hour=settings.weekly_cfo_hour,
            minute=0,
            timezone=settings.weekly_scheduler_timezone,
        ),
        id="cfo_weekly",
        replace_existing=True,
    )
    scheduler.add_job(
        run_cmo,
        CronTrigger(
            day_of_week=settings.weekly_cmo_day_of_week,
            hour=settings.weekly_cmo_hour,
            minute=0,
            timezone=settings.weekly_scheduler_timezone,
        ),
        id="cmo_weekly",
        replace_existing=True,
    )
    scheduler.add_job(
        run_ceo,
        CronTrigger(
            day_of_week=settings.weekly_ceo_day_of_week,
            hour=settings.weekly_ceo_hour,
            minute=0,
            timezone=settings.weekly_scheduler_timezone,
        ),
        id="ceo_weekly",
        replace_existing=True,
    )

    # Hourly cost monitor
    scheduler.add_job(
        run_cost_monitor,
        CronTrigger(minute=0, timezone="UTC"),
        id="cost_monitor",
        replace_existing=True,
    )

    hours = [
        int(hour.strip())
        for hour in settings.prospecting_schedule_hours_roberts.split(",")
        if hour.strip()
    ]
    for hour in hours:
        scheduler.add_job(
            run_roberts_prospecting_batch,
            CronTrigger(hour=hour, minute=0, timezone=settings.prospecting_schedule_timezone),
            id=f"roberts_prospecting_{hour:02d}00",
            replace_existing=True,
        )

    log.info("scheduler_jobs_registered", job_count=len(scheduler.get_jobs()))
    return scheduler
