from contextlib import asynccontextmanager
from urllib.parse import urlparse

import structlog
from fastapi import FastAPI
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from maestro.config import get_settings
from maestro.graph import setup_checkpointer
from maestro.schedulers.weekly import setup_scheduler
from maestro.utils.llm import setup_langsmith
from maestro.utils.logging import configure_logging
from maestro.webhooks import ghl_router, gmail_router, telegram_router


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    setup_langsmith(settings)
    log.info("maestro_starting", env=settings.app_env, dry_run=settings.dry_run)

    await setup_checkpointer(settings)

    scheduler = None
    if settings.scheduler_enabled:
        scheduler = setup_scheduler()
        scheduler.start()
        log.info("scheduler_started")
    else:
        log.info("scheduler_disabled")

    yield

    if scheduler:
        scheduler.shutdown(wait=False)
    log.info("maestro_stopped")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

    # Restrict to expected hostname (prevents Host header injection)
    parsed = urlparse(settings.webhook_base_url)
    allowed_hosts = ["localhost", "127.0.0.1", "testserver"]
    if parsed.hostname:
        allowed_hosts.append(parsed.hostname)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
    app.add_middleware(SecurityHeadersMiddleware)

    app.include_router(telegram_router)
    app.include_router(ghl_router)
    app.include_router(gmail_router)

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
