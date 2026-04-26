from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from maestro.config import get_settings
from maestro.schedulers.weekly import setup_scheduler
from maestro.utils.logging import configure_logging
from maestro.webhooks import ghl_router, telegram_router

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    log.info("maestro_starting", env=settings.app_env, dry_run=settings.dry_run)

    scheduler = setup_scheduler()
    scheduler.start()
    log.info("scheduler_started")

    yield

    scheduler.shutdown(wait=False)
    log.info("maestro_stopped")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    app.include_router(telegram_router)
    app.include_router(ghl_router)

    @app.get("/health")
    async def health() -> dict:
        return {
            "status": "ok",
            "app": settings.app_name,
            "env": settings.app_env,
            "dry_run": settings.dry_run,
        }

    return app


app = create_app()
