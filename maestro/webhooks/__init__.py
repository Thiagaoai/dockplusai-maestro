from maestro.webhooks.ghl import router as ghl_router
from maestro.webhooks.gmail import router as gmail_router
from maestro.webhooks.resend import router as resend_router
from maestro.webhooks.telegram import router as telegram_router

__all__ = ["ghl_router", "gmail_router", "resend_router", "telegram_router"]
