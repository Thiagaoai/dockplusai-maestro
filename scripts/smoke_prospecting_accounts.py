"""Smoke check prospecting/search accounts without printing secrets."""

from __future__ import annotations

import asyncio
import json

import httpx

from maestro.config import get_settings
from maestro.services.apollo_web import ApolloWebProspectFinder
from maestro.services.apify_maps import ApifyProspectFinder
from maestro.services.google_places import GooglePlacesProspectFinder
from maestro.services.hunter import HunterProspectFinder
from maestro.services.perplexity import PerplexityProspectFinder
from maestro.services.tavily import TavilyProspectFinder
from maestro.tools._enrichment.apollo import search_people


async def main() -> None:
    settings = get_settings()
    results: dict[str, object] = {
        "configured": {
            "apollo": bool(settings.apollo_api_key),
            "hunter": bool(settings.hunter_api_key),
            "apify": bool(settings.apify_token),
            "perplexity": bool(settings.perplexity_api_key),
            "tavily": bool(settings.tavily_api_key),
        }
    }

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        if settings.perplexity_api_key:
            r = await client.post(
                "https://api.perplexity.ai/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.perplexity_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "sonar",
                    "messages": [{"role": "user", "content": "Reply with only: ok"}],
                    "max_tokens": 10,
                },
            )
            results["perplexity_api"] = {"status_code": r.status_code, "ok": r.status_code < 400}

        if settings.apify_token:
            r = await client.get(
                "https://api.apify.com/v2/users/me",
                headers={"Authorization": f"Bearer {settings.apify_token}"},
            )
            data = r.json().get("data", {}) if r.status_code < 400 else {}
            plan = data.get("plan") or {}
            results["apify_account"] = {
                "status_code": r.status_code,
                "ok": r.status_code < 400,
                "username": data.get("username"),
                "plan_id": plan.get("id"),
                "monthly_usage_credits_usd": plan.get("monthlyUsageCreditsUsd"),
            }

    if settings.apollo_api_key:
        people = await search_people(
            person_titles=["CEO"],
            q_keywords="operations",
            per_page=1,
            page=1,
            idempotency_key="smoke:apollo_people",
        )
        results["apollo_people_search"] = {
            "ok": not people.get("plan_limited"),
            "plan_limited": people.get("plan_limited"),
            "people_count": len(people.get("people", [])),
            "error": people.get("error"),
        }
        try:
            rows = await ApolloWebProspectFinder(settings).search_prospects(
                "hoa",
                ["Cape Cod"],
                max_results_per_location=1,
            )
            results["apollo_web_finder"] = {"ok": True, "prospects_count": len(rows)}
        except Exception as exc:
            results["apollo_web_finder"] = {"ok": False, "error": str(exc)[:300]}

    if settings.hunter_api_key:
        try:
            rows = await HunterProspectFinder(settings).search_prospects(
                "marina",
                ["Cape Cod", "South Shore", "Martha's Vineyard", "Nantucket"],
                max_results_per_location=5,
            )
            results["hunter_finder"] = {"ok": True, "prospects_count": len(rows)}
        except Exception as exc:
            results["hunter_finder"] = {"ok": False, "error": str(exc)[:300]}

    if settings.tavily_api_key:
        try:
            rows = await TavilyProspectFinder(settings).search_prospects(
                "marina",
                ["Cape Cod"],
                max_results_per_location=2,
                max_prospects=2,
            )
            results["tavily_finder"] = {"ok": True, "prospects_count": len(rows)}
        except Exception as exc:
            results["tavily_finder"] = {"ok": False, "error": str(exc)[:300]}

    if settings.google_maps_api_key:
        try:
            rows = await GooglePlacesProspectFinder(settings).search_prospects(
                "marina",
                ["Cape Cod"],
                max_results_per_location=1,
            )
            results["google_places_finder"] = {"ok": True, "prospects_count": len(rows)}
        except Exception as exc:
            results["google_places_finder"] = {"ok": False, "error": str(exc)[:300]}
    else:
        results["google_places_finder"] = {"ok": False, "error": "GOOGLE_MAPS_API_KEY not set"}

    if settings.apify_token:
        try:
            rows = await ApifyProspectFinder(settings).search_prospects(
                "marina",
                ["Cape Cod"],
                max_results_per_location=1,
            )
            results["apify_finder"] = {"ok": True, "prospects_count": len(rows)}
        except Exception as exc:
            results["apify_finder"] = {"ok": False, "error": str(exc)[:300]}

    if settings.perplexity_api_key:
        try:
            rows = await PerplexityProspectFinder(settings).search_prospects(
                "hoa",
                ["Cape Cod"],
                max_results_per_location=1,
            )
            results["perplexity_finder"] = {
                "ok": True,
                "prospects_count": len(rows),
                "note": "0 can mean search worked but no public email was scraped from returned websites.",
            }
        except Exception as exc:
            results["perplexity_finder"] = {"ok": False, "error": str(exc)[:300]}

    print(json.dumps(results, indent=2, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())
