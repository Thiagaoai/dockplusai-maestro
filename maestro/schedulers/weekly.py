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
from maestro.config import get_settings
from maestro.memory.redis_session import acquire_cron_lock, is_stopped, release_cron_lock
from maestro.profiles import load_profile
from maestro.repositories import store

log = structlog.get_logger()

scheduler = AsyncIOScheduler()


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
        for business in ["roberts", "dockplusai"]:
            result, run = await CFOAgent(settings, load_profile(business)).run()
            await store.add_agent_run(run)
            await store.add_business_metric(
                {
                    "business": business,
                    "metric_type": "cfo_weekly",
                    "metric_data": result.data,
                    "generated_by": "cfo",
                }
            )
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
        for business in ["roberts", "dockplusai"]:
            result, run = await CMOAgent(settings, load_profile(business)).run()
            await store.add_agent_run(run)
            if result.approval:
                await store.create_approval(result.approval)
            await store.add_business_metric(
                {
                    "business": business,
                    "metric_type": "cmo_weekly",
                    "metric_data": result.data,
                    "generated_by": "cmo",
                }
            )
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
        for business in ["roberts", "dockplusai"]:
            result, run = await CEOAgent(settings, load_profile(business)).run()
            await store.add_agent_run(run)
            await store.add_business_metric(
                {
                    "business": business,
                    "metric_type": "ceo_weekly",
                    "metric_data": result.data,
                    "generated_by": "ceo",
                }
            )
        log.info("cron_ceo_weekly_done")
    except Exception as exc:
        log.error("cron_ceo_weekly_error", error=str(exc))
    finally:
        release_cron_lock("ceo_weekly")


# ── cost monitor ──────────────────────────────────────────────────────────────

async def run_cost_monitor() -> None:
    """Hourly: check daily spend, send alert or trigger kill switch."""
    if not acquire_cron_lock("cost_monitor", timeout=50):
        return
    try:
        # TODO: query daily_costs table, compare vs settings thresholds
        settings = get_settings()
        log.info("cron_cost_monitor_run",
                 alert_threshold=settings.daily_cost_alert_usd,
                 kill_threshold=settings.daily_cost_kill_usd)
    except Exception as exc:
        log.error("cron_cost_monitor_error", error=str(exc))
    finally:
        release_cron_lock("cost_monitor")


# ── scheduler setup ───────────────────────────────────────────────────────────

def setup_scheduler() -> AsyncIOScheduler:
    """Wire all cron jobs. Call once at app startup."""
    # Weekly jobs — UTC times
    scheduler.add_job(run_cfo, CronTrigger(day_of_week="mon", hour=7, minute=0, timezone="UTC"), id="cfo_weekly")
    scheduler.add_job(run_cmo, CronTrigger(day_of_week="mon", hour=8, minute=0, timezone="UTC"), id="cmo_weekly")
    scheduler.add_job(run_ceo, CronTrigger(day_of_week="mon", hour=9, minute=0, timezone="UTC"), id="ceo_weekly")

    # Hourly cost monitor
    scheduler.add_job(run_cost_monitor, CronTrigger(minute=0, timezone="UTC"), id="cost_monitor")

    log.info("scheduler_jobs_registered", job_count=len(scheduler.get_jobs()))
    return scheduler
