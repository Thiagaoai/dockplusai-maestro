import hashlib
import hmac

from fastapi import Header, HTTPException, Request, status

from maestro.config import Settings


def verify_telegram_secret(
    header_secret: str | None,
    expected_secret: str,
) -> None:
    if not expected_secret:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="secret_unset")
    if not header_secret or not hmac.compare_digest(header_secret, expected_secret):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_telegram_secret")


def verify_telegram_chat(chat_id: int, allowed_chat_id: int) -> None:
    if allowed_chat_id and chat_id != allowed_chat_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="unauthorized_chat")


def compute_hmac_sha256(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def verify_hmac_signature(secret: str, body: bytes, signature: str | None) -> None:
    if not secret:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="secret_unset")
    expected = compute_hmac_sha256(secret, body)
    supplied = (signature or "").removeprefix("sha256=")
    if not supplied or not hmac.compare_digest(expected, supplied):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_signature")


async def require_telegram_auth(
    request: Request,
    settings: Settings,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> None:
    verify_telegram_secret(x_telegram_bot_api_secret_token, settings.telegram_webhook_secret)
    payload = await request.json()
    message = payload.get("message") or payload.get("callback_query", {}).get("message") or {}
    chat = message.get("chat") or {}
    chat_id = int(chat.get("id") or 0)
    verify_telegram_chat(chat_id, settings.telegram_thiago_chat_id)
