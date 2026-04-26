#!/usr/bin/env python
"""One-time script to register Gmail push notifications via Google Pub/Sub.

Run once after setting up OAuth credentials and Pub/Sub topic:

    python scripts/setup_gmail_watch.py

Prerequisites:
1. Create a Google Cloud project and enable Gmail API + Cloud Pub/Sub API
2. Create a service account (or OAuth 2.0 client) — download JSON
3. Run OAuth flow to get GOOGLE_REFRESH_TOKEN:
   - Use Google OAuth Playground or a local script
4. Create a Pub/Sub topic, e.g.: projects/YOUR_PROJECT/topics/maestro-gmail
5. Grant the Gmail service account (gmail-api-push@system.gserviceaccount.com)
   Pub/Sub Publisher role on that topic
6. Add GMAIL_WEBHOOK_SECRET to .env and set the Pub/Sub push URL to:
   https://your-domain.com/webhooks/gmail?token=YOUR_SECRET

After setup, Gmail watch expires every 7 days — re-run this script weekly,
or add a scheduler job that calls gmail.setup_watch() automatically.
"""
import asyncio
import os
import sys

sys.path.insert(0, ".")

from dotenv import load_dotenv

load_dotenv()

from maestro.config import get_settings
from maestro.services.gmail import GmailClient


async def main() -> None:
    get_settings.cache_clear()
    settings = get_settings()

    gmail = GmailClient(settings)
    if not gmail.is_configured():
        print("ERROR: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN must be set.")
        sys.exit(1)

    topic = os.getenv("GMAIL_PUBSUB_TOPIC", "")
    if not topic:
        print("ERROR: GMAIL_PUBSUB_TOPIC not set. Example: projects/my-project/topics/maestro-gmail")
        sys.exit(1)

    import httpx

    async with httpx.AsyncClient() as client:
        result = await gmail.setup_watch(client, topic)

    history_id = result.get("historyId")
    expiration = result.get("expiration")
    print(f"Gmail watch registered.")
    print(f"  historyId  : {history_id}")
    print(f"  expiration : {expiration} (ms since epoch — renew before this)")
    print()
    print("Save this history ID to Redis so the webhook knows where to start:")
    print(f"  redis-cli set 'session:{\"gmail:history_id\"}' '{{\"history_id\":\"{history_id}\"}}'")


if __name__ == "__main__":
    asyncio.run(main())
