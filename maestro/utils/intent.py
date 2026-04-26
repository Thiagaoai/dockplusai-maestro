from __future__ import annotations

import json
import re
from dataclasses import dataclass

import httpx
import structlog

from maestro.config import Settings

log = structlog.get_logger()

_SYSTEM_PROMPT = """\
You are MAESTRO's intent classifier. Thiago sends messages in Portuguese or English via Telegram.

Extract the intent and return ONLY a valid JSON object — no explanation, no markdown, no extra text.

Actions:
- "prospect_web"   → search for prospects online
                     fields: source (default "tavily"), target (type of business, may be empty string)
- "prospect_batch" → run Roberts owned-list email batch
                     fields: mode ("owned"|"web"|"hybrid", default "owned"), batch_size (int, optional)
- "create_post"    → create a social media post (Instagram) with AI-generated image, caption, hashtags
                     fields: topic (what the post is about, in English), business ("roberts"|"dockplusai", default "roberts")
- "stop"           → pause all MAESTRO agents
- "start"          → resume all MAESTRO agents
- "unknown"        → everything else (general questions, status, chat)

Sources: tavily, google, hunter, apollo, apify, perplexity

Target is the type of business to prospect. Any business type counts.
Common examples: hoa, condo, school, hospital, hospice, hotel, resort, marina, church,
day care, restaurant, senior living, senior center, office park, campground, wedding venue,
property manager, gas station, facility, gym, spa, country club, brewery, winery, event venue,
real estate developer, yacht club, vacation rental, nursing home, assisted living, preschool.
Normalize to English (escola→school, hotel→hotel, posto de gasolina→gas station,
creche→day care, asilo→nursing home, iate clube→yacht club, etc.)

Examples:
"quero prospectar escolas"             → {"action":"prospect_web","source":"tavily","target":"school"}
"busca hotéis com perplexity"          → {"action":"prospect_web","source":"perplexity","target":"hotel"}
"prospecta marinas usando o google"    → {"action":"prospect_web","source":"google","target":"marina"}
"quero prospectar"                     → {"action":"prospect_web","source":"tavily","target":""}
"hoa com apollo"                       → {"action":"prospect_web","source":"apollo","target":"hoa"}
"posto de gasolina"                    → {"action":"prospect_web","source":"tavily","target":"gas station"}
"hospices no cape usando hunter"       → {"action":"prospect_web","source":"hunter","target":"hospice"}
"para tudo"                            → {"action":"stop"}
"pode continuar"                       → {"action":"start"}
"roda um batch de 5"                   → {"action":"prospect_batch","mode":"owned","batch_size":5}
"roda o batch web do roberts"          → {"action":"prospect_batch","mode":"web"}
"cria um post sobre jardinagem"        → {"action":"create_post","topic":"garden design","business":"roberts"}
"faz um post de limpeza de primavera"  → {"action":"create_post","topic":"spring cleanup","business":"roberts"}
"post dockplus sobre automação com IA" → {"action":"create_post","topic":"AI automation","business":"dockplusai"}
"quero um post sobre paisagismo"       → {"action":"create_post","topic":"landscaping","business":"roberts"}
"me fala sobre o maestro"              → {"action":"unknown"}
"qual o status?"                       → {"action":"unknown"}
"""

_JSON_RE = re.compile(r"\{[^{}]+\}", re.DOTALL)

_VALID_ACTIONS = {"prospect_web", "prospect_batch", "create_post", "stop", "start", "unknown"}
_VALID_SOURCES = {"tavily", "google", "hunter", "apollo", "apify", "perplexity"}
_VALID_MODES = {"owned", "web", "hybrid"}


@dataclass
class TelegramIntent:
    action: str
    source: str = "tavily"
    target: str = ""
    mode: str = "owned"
    batch_size: int | None = None
    topic: str = ""
    business: str = "roberts"


async def parse_telegram_intent(text: str, settings: Settings) -> TelegramIntent:
    """Classify a free-text Telegram message into a structured intent using Claude Haiku."""
    if not settings.anthropic_api_key:
        log.warning("intent_classifier_no_api_key")
        return TelegramIntent(action="unknown")

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": settings.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 120,
                    "system": _SYSTEM_PROMPT,
                    "messages": [{"role": "user", "content": text}],
                },
            )
        if r.status_code >= 400:
            log.warning("intent_classifier_api_error", status=r.status_code, body=r.text[:200])
            return TelegramIntent(action="unknown")

        raw = r.json().get("content", [{}])[0].get("text", "").strip()
        log.debug("intent_classifier_raw", raw=raw)
        m = _JSON_RE.search(raw)
        if not m:
            log.warning("intent_classifier_no_json", raw=raw[:200])
            return TelegramIntent(action="unknown")

        data = json.loads(m.group())

        action = data.get("action", "unknown")
        if action not in _VALID_ACTIONS:
            action = "unknown"

        source = str(data.get("source") or "tavily").strip()
        if source not in _VALID_SOURCES:
            source = "tavily"

        mode = str(data.get("mode") or "owned").strip()
        if mode not in _VALID_MODES:
            mode = "owned"

        batch_size: int | None = None
        raw_bs = data.get("batch_size")
        if raw_bs is not None:
            try:
                batch_size = int(raw_bs)
            except (ValueError, TypeError):
                pass

        business = str(data.get("business") or "roberts").strip()
        if business not in {"roberts", "dockplusai"}:
            business = "roberts"

        intent = TelegramIntent(
            action=action,
            source=source,
            target=str(data.get("target") or "").strip(),
            mode=mode,
            batch_size=batch_size,
            topic=str(data.get("topic") or "").strip(),
            business=business,
        )
        log.info("intent_classified", text=text[:80], action=action, target=intent.target, source=source)
        return intent

    except Exception as exc:
        log.warning("intent_classifier_exception", error=str(exc), text=text[:80])
        return TelegramIntent(action="unknown")
