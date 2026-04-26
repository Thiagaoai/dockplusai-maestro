#!/usr/bin/env python3
"""
Register the Telegram webhook with the Telegram Bot API.
Run this once after the server is deployed and DNS resolves.

Usage:
    python scripts/register_telegram_webhook.py
    python scripts/register_telegram_webhook.py --delete   # remove webhook
    python scripts/register_telegram_webhook.py --info     # check current webhook
"""
import argparse
import os
import sys

import httpx
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL", "")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def get_info() -> None:
    r = httpx.get(f"{TELEGRAM_API}/getWebhookInfo")
    r.raise_for_status()
    info = r.json().get("result", {})
    print("=== Webhook atual ===")
    print(f"URL:            {info.get('url') or '(nenhum)'}")
    print(f"Pending updates: {info.get('pending_update_count', 0)}")
    print(f"Last error:     {info.get('last_error_message') or 'none'}")
    print(f"Last error date: {info.get('last_error_date') or 'n/a'}")


def register() -> None:
    if not BOT_TOKEN:
        sys.exit("TELEGRAM_BOT_TOKEN não está definido no .env")
    if not WEBHOOK_BASE_URL or "localhost" in WEBHOOK_BASE_URL:
        sys.exit(f"WEBHOOK_BASE_URL deve ser uma URL pública HTTPS. Atual: {WEBHOOK_BASE_URL!r}")

    webhook_url = f"{WEBHOOK_BASE_URL.rstrip('/')}/webhooks/telegram"
    payload: dict = {
        "url": webhook_url,
        "allowed_updates": ["message", "callback_query"],
        "drop_pending_updates": False,
    }
    if WEBHOOK_SECRET:
        payload["secret_token"] = WEBHOOK_SECRET

    print(f"Registrando webhook: {webhook_url}")
    r = httpx.post(f"{TELEGRAM_API}/setWebhook", json=payload)
    r.raise_for_status()
    result = r.json()
    if result.get("ok"):
        print("✅ Webhook registrado com sucesso!")
        get_info()
    else:
        print(f"❌ Erro: {result}")
        sys.exit(1)


def delete() -> None:
    r = httpx.post(f"{TELEGRAM_API}/deleteWebhook", json={"drop_pending_updates": False})
    r.raise_for_status()
    print("✅ Webhook removido.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--delete", action="store_true", help="Remove o webhook")
    parser.add_argument("--info", action="store_true", help="Mostra o webhook atual")
    args = parser.parse_args()

    if args.delete:
        delete()
    elif args.info:
        get_info()
    else:
        register()
