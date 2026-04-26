from html import escape
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from maestro.config import Settings
from maestro.profiles import load_profile
from maestro.schemas.events import AgentRunRecord, ApprovalRequest, LeadRecord
from maestro.services.prospecting import interleave_prospect_sources, prospect_queue_item
from maestro.services.tavily import TavilyProspectFinder, WebProspect
from maestro.tools._enrichment.apollo import search_people

KNOWN_SOURCES = {"tavily", "google", "hunter", "apollo", "apify", "perplexity"}


def _get_finder(source: str, settings):
    if source == "google":
        from maestro.services.google_places import GooglePlacesProspectFinder
        return GooglePlacesProspectFinder(settings)
    if source == "hunter":
        from maestro.services.hunter import HunterProspectFinder
        return HunterProspectFinder(settings)
    if source == "apollo":
        from maestro.services.apollo_web import ApolloWebProspectFinder
        return ApolloWebProspectFinder(settings)
    if source == "apify":
        from maestro.services.apify_maps import ApifyProspectFinder
        return ApifyProspectFinder(settings)
    if source == "perplexity":
        from maestro.services.perplexity import PerplexityProspectFinder
        return PerplexityProspectFinder(settings)
    return None  # caller uses self.web_finder (Tavily default)

DOCKPLUS_ICP_TITLES = [
    "CEO",
    "COO",
    "Founder",
    "Owner",
    "Operations Manager",
    "Director of Operations",
    "VP of Operations",
    "General Manager",
]


class ProspectingAgent:
    def __init__(self, settings: Settings, store, web_finder: TavilyProspectFinder | None = None) -> None:
        self.settings = settings
        self.store = store
        self.web_finder = web_finder or TavilyProspectFinder(settings)

    async def prepare_dockplusai_apollo_batch(
        self,
        person_titles: list[str] | None = None,
        batch_size: int = 10,
        page: int = 1,
    ) -> tuple[ApprovalRequest | None, AgentRunRecord]:
        business = "dockplusai"
        titles = person_titles or DOCKPLUS_ICP_TITLES
        result = await search_people(
            person_titles=titles,
            q_keywords="small business operations",
            per_page=batch_size,
            page=page,
        )

        if result.get("plan_limited"):
            run = AgentRunRecord(
                business=business,
                agent_name="prospecting",
                input=f"apollo_search titles={titles} page={page}",
                output='{"status":"plan_limited","reason":"Apollo people search requires paid plan"}',
                profit_signal="pipeline",
                prompt_version=self.settings.prompt_version,
                dry_run=self.settings.dry_run,
            )
            return None, run

        people = result.get("people", [])
        if not people:
            run = AgentRunRecord(
                business=business,
                agent_name="prospecting",
                input=f"apollo_search titles={titles} page={page}",
                output=f'{{"status":"empty","page":{page}}}',
                profit_signal="pipeline",
                prompt_version=self.settings.prompt_version,
                dry_run=self.settings.dry_run,
            )
            return None, run

        source_refs = await self._queue_apollo_prospects(business, people, titles)
        selected = [
            item
            for item in await self.store.list_prospect_queue(business, status="queued", limit=batch_size, source_type="apollo")
            if item.get("source_ref") in set(source_refs)
        ][:batch_size]

        if not selected:
            run = AgentRunRecord(
                business=business,
                agent_name="prospecting",
                input=f"apollo_search titles={titles} page={page}",
                output='{"status":"empty","reason":"all already in queue"}',
                profit_signal="pipeline",
                prompt_version=self.settings.prompt_version,
                dry_run=self.settings.dry_run,
            )
            return None, run

        return await self._dockplus_approval_from_selected(selected, titles, page)

    async def _queue_apollo_prospects(
        self,
        business: str,
        people: list[dict[str, Any]],
        titles: list[str],
    ) -> list[str]:
        queued_refs: list[str] = []
        for person in people:
            email = person.get("email") or person.get("personal_email")
            if not email:
                continue
            event_id = f"apollo:{business}:{person.get('apollo_id') or uuid5(NAMESPACE_URL, email).hex}"
            lead = LeadRecord(
                id=uuid5(NAMESPACE_URL, event_id),
                event_id=event_id,
                business=business,
                name=person.get("name"),
                email=email,
                source="apollo_people_search",
                message=person.get("title"),
                raw={
                    "apollo_id": person.get("apollo_id"),
                    "title": person.get("title"),
                    "company": person.get("company"),
                    "linkedin_url": person.get("linkedin_url"),
                    "location": person.get("location"),
                    "icp_titles": titles,
                },
            )
            await self.store.upsert_lead(lead)
            item = prospect_queue_item(
                business=business,
                lead=lead,
                source_name="apollo_people_search",
                source_ref=event_id,
                source_type="apollo",
            )
            company = person.get("company") or {}
            item["payload"] = {
                **item["payload"],
                "title": person.get("title"),
                "company_name": company.get("name"),
                "company_website": company.get("website"),
                "company_industry": company.get("industry"),
                "company_employees": company.get("employee_count"),
                "linkedin_url": person.get("linkedin_url"),
                "location": person.get("location"),
            }
            await self.store.upsert_prospect_queue_item(item)
            queued_refs.append(event_id)
        return queued_refs

    async def _dockplus_approval_from_selected(
        self,
        selected: list[dict[str, Any]],
        titles: list[str],
        page: int,
    ) -> tuple[ApprovalRequest, AgentRunRecord]:
        business = "dockplusai"
        profile = load_profile(business)
        website = profile.contact.website or "https://dockplus.ai"
        prospects = [self._apollo_prospect_preview(item) for item in selected]
        source_refs = [item["source_ref"] for item in selected]
        cc = [self.settings.resend_reply_to_dockplusai] if self.settings.resend_reply_to_dockplusai else []

        preview = {
            "campaign": {
                "name": "DockPlus AI Apollo B2B Prospecting",
                "source": "apollo_people_search",
                "icp_titles": titles,
                "page": page,
                "business": business,
                "batch_size": len(selected),
                "schedule": "09:00, 14:00 America/New_York",
                "offer": "Free AI audit — identify 3 automation opportunities in 30 min",
                "cta_url": website,
                "tone": "Strategic, direct, ROI-first cold outreach",
            },
            "email": {
                "subject": self._dockplus_subject(),
                "text": self._dockplus_text_body(profile.business_name, website),
                "html": self._dockplus_html_body(profile.business_name, website),
                "cc": cc,
            },
            "prospects": prospects,
            "source_refs": source_refs,
            "dry_run": self.settings.dry_run,
            "profit_signal": "pipeline",
        }
        approval = ApprovalRequest(
            business=business,
            event_id=f"prospecting:{business}:{uuid4()}",
            action="prospecting_apollo_batch_send",
            preview=preview,
        )
        run = AgentRunRecord(
            business=business,
            agent_name="prospecting",
            input=f"apollo_batch titles={titles} size={len(selected)} page={page}",
            output=approval.model_dump_json(),
            profit_signal="pipeline",
            prompt_version=self.settings.prompt_version,
            dry_run=self.settings.dry_run,
        )
        await self.store.update_prospect_queue_status(business, source_refs, "drafted")
        return approval, run

    def _apollo_prospect_preview(self, item: dict[str, Any]) -> dict[str, Any]:
        payload = item.get("payload") or {}
        return {
            "source_type": item.get("source_type"),
            "source_ref": item.get("source_ref"),
            "lead_id": item.get("lead_id"),
            "name": payload.get("lead_name"),
            "title": payload.get("title"),
            "company_name": payload.get("company_name"),
            "company_industry": payload.get("company_industry"),
            "company_employees": payload.get("company_employees"),
            "linkedin_url": payload.get("linkedin_url"),
            "has_email": payload.get("has_email", False),
        }

    def _dockplus_subject(self) -> str:
        return "Quick question about your ops workflow"

    def _dockplus_text_body(self, business_name: str, website_url: str) -> str:
        return (
            "Hi,\n\n"
            f"This is {business_name}. We help small and mid-size companies identify where manual "
            "work is slowing down revenue — follow-up gaps, reporting bottlenecks, ops that don't scale.\n\n"
            "We typically find 3-5 automation opportunities in the first 30-minute conversation, "
            "and at least one of them pays for itself in the first month.\n\n"
            "If that sounds relevant to where your team is right now, I'm happy to take a look — "
            f"no pitch, just a straight analysis: {website_url}\n\n"
            "Best,\nDockPlus AI\n\n"
            "If this is not relevant, reply STOP and we will not follow up."
        )

    def _dockplus_html_body(self, business_name: str, website_url: str) -> str:
        safe_url = escape(website_url)
        safe_name = escape(business_name)
        return f"""<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#f0f4ff;font-family:Arial,Helvetica,sans-serif;color:#1f2933;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f0f4ff;padding:24px 0;">
      <tr><td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:620px;background:#fff;border:1px solid #d0d7e6;">
          <tr><td style="padding:28px 30px 12px;">
            <div style="font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:#64748b;">AI Automation Audit</div>
            <h1 style="font-size:26px;line-height:1.2;margin:10px 0;color:#172033;">Where is manual work slowing your revenue?</h1>
            <p style="font-size:16px;line-height:1.55;color:#334155;margin:0;">{safe_name} maps operational bottlenecks to revenue — then builds the automation to fix them.</p>
          </td></tr>
          <tr><td style="padding:8px 30px 4px;">
            <p style="font-size:16px;line-height:1.6;margin:0 0 14px;">Hi,</p>
            <p style="font-size:16px;line-height:1.6;margin:0 0 14px;">Most growing companies have 3-5 spots where manual work is quietly killing speed: slow follow-up, reports that live in someone's head, leads that fall through the cracks.</p>
            <p style="font-size:16px;line-height:1.6;margin:0 0 18px;">We find those spots in a 30-minute conversation and show exactly what automation would do — not in theory, in dollars and hours saved per week.</p>
            <table role="presentation" cellspacing="0" cellpadding="0" style="margin:22px 0;"><tr><td style="background:#1e3a8a;padding:13px 18px;"><a href="{safe_url}" style="color:#fff;text-decoration:none;font-size:16px;font-weight:bold;">Book a Free Audit</a></td></tr></table>
            <p style="font-size:14px;line-height:1.5;color:#64748b;margin:0 0 20px;">No pitch. Just a straight analysis of where the biggest opportunities are.</p>
          </td></tr>
          <tr><td style="padding:18px 30px 28px;border-top:1px solid #d0d7e6;">
            <p style="font-size:15px;line-height:1.5;margin:0;color:#334155;">Best,<br>{safe_name}</p>
            <p style="font-size:12px;line-height:1.5;color:#64748b;margin:18px 0 0;">If this is not relevant, reply STOP and we will not follow up.</p>
          </td></tr>
        </table>
      </td></tr>
    </table>
  </body>
</html>"""

    async def prepare_roberts_batch(
        self,
        batch_size: int | None = None,
        mode: str = "owned",
    ) -> tuple[ApprovalRequest | None, AgentRunRecord]:
        business = "roberts"
        size = batch_size or self.settings.prospecting_batch_size_roberts
        selected = await self._select_batch(business, size, mode)

        if not selected:
            run = AgentRunRecord(
                business=business,
                agent_name="prospecting",
                input=f"prepare_roberts_batch mode={mode}",
                output=f'{{"status":"empty","mode":"{mode}"}}',
                profit_signal="pipeline",
                prompt_version=self.settings.prompt_version,
                dry_run=self.settings.dry_run,
            )
            return None, run

        return await self._approval_from_selected(
            business=business,
            selected=selected,
            size=size,
            mode=mode,
        )

    async def prepare_roberts_web_search_batch(
        self,
        target: str,
        batch_size: int | None = None,
        source: str = "tavily",
    ) -> tuple[ApprovalRequest | None, AgentRunRecord]:
        business = "roberts"
        size = batch_size or self.settings.prospecting_batch_size_roberts
        locations = self._web_locations()
        finder = _get_finder(source, self.settings) or self.web_finder
        max_results_per_location = max(1, min(3, size))
        try:
            if isinstance(finder, TavilyProspectFinder):
                found = await finder.search_prospects(
                    target,
                    locations,
                    max_results_per_location=max_results_per_location,
                    max_prospects=size,
                )
            else:
                found = await finder.search_prospects(
                    target,
                    locations,
                    max_results_per_location=max_results_per_location,
                )
        except Exception as exc:
            run = AgentRunRecord(
                business=business,
                agent_name="prospecting",
                input=f"web_search source={source} target={target}",
                output=f'{{"status":"error","source":"{source}","error":"{str(exc)[:200]}"}}',
                profit_signal="pipeline",
                prompt_version=self.settings.prompt_version,
                dry_run=self.settings.dry_run,
            )
            return None, run

        found = found[:size]
        queued_refs = await self._queue_web_prospects(
            business,
            target,
            found,
            source=source,
            max_items=size,
        )
        if not queued_refs:
            run = AgentRunRecord(
                business=business,
                agent_name="prospecting",
                input=f"web_search source={source} target={target}",
                output=f'{{"status":"empty","source":"{source}","target":"{target}","locations":{locations!r}}}',
                profit_signal="pipeline",
                prompt_version=self.settings.prompt_version,
                dry_run=self.settings.dry_run,
            )
            return None, run
        selected = await self.store.list_prospect_queue(
            business,
            status="queued",
            limit=size,
            source_type="scrape",
        )
        selected = [item for item in selected if item.get("source_ref") in set(queued_refs)][:size]
        if not selected:
            run = AgentRunRecord(
                business=business,
                agent_name="prospecting",
                input=f"web_search source={source} target={target}",
                output=f'{{"status":"empty","source":"{source}","target":"{target}","locations":{locations!r}}}',
                profit_signal="pipeline",
                prompt_version=self.settings.prompt_version,
                dry_run=self.settings.dry_run,
            )
            return None, run
        return await self._approval_from_selected(
            business=business,
            selected=selected,
            size=size,
            mode="web",
            target=target,
            locations=locations,
            source=source,
        )

    async def _select_batch(self, business: str, size: int, mode: str) -> list[dict[str, Any]]:
        if mode == "web":
            return await self.store.list_prospect_queue(
                business, status="queued", limit=size, source_type="scrape"
            )
        if mode == "hybrid":
            owned_target = max(size, self.settings.prospecting_customer_per_scrape_cycle * size)
            scrape_target = max(size, self.settings.prospecting_scrape_per_cycle * size)
            owned = await self.store.list_prospect_queue(
                business, status="queued", limit=owned_target, source_type="customer_file"
            )
            scrape = await self.store.list_prospect_queue(
                business, status="queued", limit=scrape_target, source_type="scrape"
            )
            return interleave_prospect_sources(
                owned,
                scrape,
                owned_per_cycle=self.settings.prospecting_customer_per_scrape_cycle,
                scrape_per_cycle=self.settings.prospecting_scrape_per_cycle,
            )[:size]
        return await self.store.list_prospect_queue(
            business, status="queued", limit=size, source_type="customer_file"
        )

    async def _approval_from_selected(
        self,
        business: str,
        selected: list[dict[str, Any]],
        size: int,
        mode: str,
        target: str | None = None,
        locations: list[str] | None = None,
        source: str = "tavily",
    ) -> tuple[ApprovalRequest, AgentRunRecord]:
        profile = load_profile(business)
        subject = self._subject(target)
        text_body = self._text_body(profile.business_name, target)
        html_body = self._html_body(profile.business_name, target)
        prospects = [self._prospect_preview(item) for item in selected]
        source_refs = [item["source_ref"] for item in selected]
        force_real_send = mode == "web"
        cc = [self.settings.resend_reply_to_roberts] if self.settings.resend_reply_to_roberts else []
        preview = {
            "campaign": {
                "name": self._campaign_name(target, source),
                "mode": mode,
                "flow": "roberts web" if mode == "web" else "roberts 10",
                "target": target,
                "locations": locations or [],
                "business": business,
                "batch_size": len(selected),
                "schedule": "08:00, 11:00, 15:00, 17:00 America/New_York",
                "offer": f"{self.settings.roberts_promo_discount_percent}% off for new customers",
                "cta_url": self.settings.roberts_website_url,
                "tone": "natural American sales tone for Cape Cod, MA homeowners and property managers",
            },
            "email": {
                "subject": subject,
                "text": text_body,
                "html": html_body,
                "cc": cc,
            },
            "prospects": prospects,
            "source_refs": source_refs,
            "dry_run": self.settings.dry_run and not force_real_send,
            "force_real_send": force_real_send,
            "profit_signal": "pipeline",
        }
        approval = ApprovalRequest(
            business=business,
            event_id=f"prospecting:{business}:{uuid4()}",
            action="prospecting_batch_send_html",
            preview=preview,
        )
        run = AgentRunRecord(
            business=business,
            agent_name="prospecting",
            input=f"prepare batch size={size} mode={mode} target={target}",
            output=approval.model_dump_json(),
            profit_signal="pipeline",
            prompt_version=self.settings.prompt_version,
            dry_run=self.settings.dry_run,
        )
        await self.store.update_prospect_queue_status(business, source_refs, "drafted")
        return approval, run

    def _prospect_preview(self, item: dict[str, Any]) -> dict[str, Any]:
        payload = item.get("payload") or {}
        return {
            "source_type": item.get("source_type"),
            "source_name": item.get("source_name"),
            "source_ref": item.get("source_ref"),
            "lead_id": item.get("lead_id"),
            "name": payload.get("lead_name"),
            "property_name": payload.get("property_name") or payload.get("lead_name"),
            "source_url": payload.get("source_url"),
            "verification_note": payload.get("verification_note"),
            "has_email": payload.get("has_email", False),
            "has_phone": payload.get("has_phone", False),
        }

    async def _queue_web_prospects(
        self,
        business: str,
        target: str,
        prospects: list[WebProspect],
        source: str = "tavily",
        max_items: int | None = None,
    ) -> list[str]:
        source_name = f"{source}_web_search"
        queued_refs: list[str] = []
        for prospect in prospects:
            if max_items is not None and len(queued_refs) >= max_items:
                break
            event_id = f"{source}:{business}:{target}:{prospect.email.casefold()}"
            lead = LeadRecord(
                id=uuid5(NAMESPACE_URL, event_id),
                event_id=event_id,
                business=business,
                name=prospect.name,
                email=prospect.email,
                source=source_name,
                message=prospect.verification_note,
                status="prospect_imported",
                raw={
                    "target": prospect.target,
                    "location": prospect.location,
                    "source_url": prospect.source_url,
                    "source_title": prospect.source_title,
                    "verification": prospect.verification_note,
                    "prospect_source": source,
                    "raw_result": prospect.raw,
                },
            )
            await self.store.upsert_lead(lead)
            item = prospect_queue_item(
                business=business,
                lead=lead,
                source_name=source_name,
                source_ref=event_id,
                source_type="scrape",
            )
            item["payload"] = {
                **item["payload"],
                "property_name": prospect.name,
                "source_url": prospect.source_url,
                "verification_note": prospect.verification_note,
                "target": prospect.target,
                "location": prospect.location,
            }
            await self.store.upsert_prospect_queue_item(item)
            queued_refs.append(event_id)
        return queued_refs

    def _web_locations(self) -> list[str]:
        return [
            location.strip()
            for location in self.settings.prospecting_web_locations_roberts.split(",")
            if location.strip()
        ]

    _HOA_TARGETS = frozenset({
        "hoa", "hoas", "homeowners association", "condo", "condominium",
        "property manager", "property management",
    })
    _INSTITUTIONAL_TARGETS = frozenset({
        "school", "day care", "daycare", "preschool", "hospital", "hospice",
        "senior living", "assisted living", "nursing home", "church",
    })
    _HOSPITALITY_TARGETS = frozenset({
        "hotel", "motel", "resort", "inn", "bed and breakfast", "marina",
        "restaurant", "brewery", "winery", "campground", "country club",
        "golf", "event venue", "wedding venue", "spa", "gym", "yacht club",
    })

    def _vertical_category(self, target: str | None) -> str:
        if not target:
            return "generic"
        normalized = target.strip().casefold()
        if normalized in self._HOA_TARGETS:
            return "hoa"
        if normalized in self._INSTITUTIONAL_TARGETS:
            return "institutional"
        if normalized in self._HOSPITALITY_TARGETS:
            return "hospitality"
        return "generic"

    def _subject(self, target: str | None = None) -> str:
        category = self._vertical_category(target)
        if category == "hoa":
            return "Cape Cod landscape help for HOA and condo communities"
        if category == "institutional":
            return "Grounds and landscape help for Cape Cod organizations"
        if category == "hospitality":
            return "Outdoor upgrades for your Cape Cod property"
        return "10% off a new landscape project on Cape Cod"

    def _campaign_name(self, target: str | None = None, source: str = "tavily") -> str:
        src_tag = f"[{source.upper()}]" if source != "tavily" else ""
        if target:
            return f"Roberts Web Prospecting - {target.strip().upper()} {src_tag}".strip()
        return "Roberts 10% New Customer Landscape Promo"

    def _text_body(self, business_name: str, target: str | None = None) -> str:
        discount = self.settings.roberts_promo_discount_percent
        url = self.settings.roberts_website_url
        category = self._vertical_category(target)

        if category == "hoa":
            return (
                "Hi there,\n\n"
                f"This is {business_name}. We help Cape Cod, South Shore, Martha's Vineyard, "
                "and Nantucket communities with practical landscape and hardscape work: patios, "
                "walkways, drainage, planting, stonework, and outdoor living upgrades.\n\n"
                f"For new association or property-management clients, we are offering {discount}% "
                "off a new approved landscape project.\n\n"
                f"See our work and request a quote here: {url}\n\n"
                "If you are the right person to talk with about exterior projects or common-area "
                "improvements, I would be glad to take a look and give you a clear next step.\n\n"
                "Best,\nRoberts Landscape\n\n"
                "If this is not relevant, reply STOP and we will not follow up."
            )

        if category == "institutional":
            return (
                "Hi there,\n\n"
                f"This is {business_name}. We work with schools, community organizations, "
                "and public properties across Cape Cod on practical grounds and landscape work: "
                "walkways, drainage, common areas, plantings, and hardscape that holds up "
                "in coastal weather.\n\n"
                f"For new clients, we are offering {discount}% off a new approved project.\n\n"
                "If you handle exterior maintenance or grounds improvements, I would be glad "
                f"to take a look and give you a straight next step: {url}\n\n"
                "Best,\nRoberts Landscape\n\n"
                "If this is not relevant, reply STOP and we will not follow up."
            )

        if category == "hospitality":
            return (
                "Hi there,\n\n"
                f"This is {business_name}. We help Cape Cod hotels, restaurants, and hospitality "
                "properties with outdoor upgrades that make a difference for guests: patios, "
                "entrance walkways, plantings, drainage, and stonework.\n\n"
                f"For new clients, we are offering {discount}% off a new approved project.\n\n"
                f"See our work and reach out here: {url}\n\n"
                "Best,\nRoberts Landscape\n\n"
                "If this is not relevant, reply STOP and we will not follow up."
            )

        return (
            "Hi there,\n\n"
            f"This is {business_name}. If you are planning a new landscape, patio, walkway, "
            f"drainage, or outdoor living project on Cape Cod, we are offering {discount}% off "
            "for new customers for a limited time.\n\n"
            "We keep the process straightforward: look at the project, talk through what will last "
            "in Cape Cod weather, and give you a clear next step.\n\n"
            f"See our work and request a quote here: {url}\n\n"
            "Best,\nRoberts Landscape\n\n"
            "If this is not relevant, reply STOP and we will not follow up."
        )

    def _html_body(self, business_name: str, target: str | None = None) -> str:
        discount = self.settings.roberts_promo_discount_percent
        url = escape(self.settings.roberts_website_url)
        safe_name = escape(business_name)
        category = self._vertical_category(target)

        if category == "hoa":
            return f"""<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#f7f7f4;font-family:Arial,Helvetica,sans-serif;color:#1f2933;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f7f7f4;padding:24px 0;">
      <tr><td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:620px;background:#fff;border:1px solid #dedbd2;">
          <tr><td style="padding:28px 30px 12px;">
            <div style="font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:#64748b;">HOA & Condo Landscape Help</div>
            <h1 style="font-size:27px;line-height:1.2;margin:10px 0;color:#172033;">A practical landscape team for coastal communities</h1>
            <p style="font-size:16px;line-height:1.55;color:#334155;margin:0;">{safe_name} helps with patios, walkways, drainage, planting, stonework, and outdoor living upgrades.</p>
          </td></tr>
          <tr><td style="padding:8px 30px 4px;">
            <p style="font-size:16px;line-height:1.6;margin:0 0 14px;">Hi there,</p>
            <p style="font-size:16px;line-height:1.6;margin:0 0 14px;">If your association or managed property is planning exterior improvements, we can take a look and give you a clear next step.</p>
            <p style="font-size:16px;line-height:1.6;margin:0 0 18px;">For new association or property-management clients, we are offering <strong>{discount}% off</strong> a new approved landscape project.</p>
            <table role="presentation" cellspacing="0" cellpadding="0" style="margin:22px 0;"><tr><td style="background:#256f46;padding:13px 18px;"><a href="{url}" style="color:#fff;text-decoration:none;font-size:16px;font-weight:bold;">Request a Quote</a></td></tr></table>
            <p style="font-size:14px;line-height:1.5;color:#64748b;margin:0 0 20px;">Final pricing requires project review. Promotion is for new clients and new approved projects.</p>
          </td></tr>
          <tr><td style="padding:18px 30px 28px;border-top:1px solid #dedbd2;">
            <p style="font-size:15px;line-height:1.5;margin:0;color:#334155;">Best,<br>Roberts Landscape</p>
            <p style="font-size:12px;line-height:1.5;color:#64748b;margin:18px 0 0;">If this is not relevant, reply STOP and we will not follow up.</p>
          </td></tr>
        </table>
      </td></tr>
    </table>
  </body>
</html>"""

        if category == "institutional":
            return f"""<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#f4f6f7;font-family:Arial,Helvetica,sans-serif;color:#1f2933;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f4f6f7;padding:24px 0;">
      <tr><td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:620px;background:#fff;border:1px solid #d5dde3;">
          <tr><td style="padding:28px 30px 12px;">
            <div style="font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:#64748b;">Cape Cod Grounds & Landscape</div>
            <h1 style="font-size:27px;line-height:1.2;margin:10px 0;color:#172033;">Practical grounds work for Cape Cod organizations</h1>
            <p style="font-size:16px;line-height:1.55;color:#334155;margin:0;">{safe_name} works with schools, community organizations, and public properties on walkways, drainage, plantings, and hardscape.</p>
          </td></tr>
          <tr><td style="padding:8px 30px 4px;">
            <p style="font-size:16px;line-height:1.6;margin:0 0 14px;">Hi there,</p>
            <p style="font-size:16px;line-height:1.6;margin:0 0 14px;">If you handle exterior maintenance or grounds improvements, we can take a look at your property and give you a straight next step.</p>
            <p style="font-size:16px;line-height:1.6;margin:0 0 18px;">For new clients, we are offering <strong>{discount}% off</strong> a new approved landscape project.</p>
            <table role="presentation" cellspacing="0" cellpadding="0" style="margin:22px 0;"><tr><td style="background:#256f46;padding:13px 18px;"><a href="{url}" style="color:#fff;text-decoration:none;font-size:16px;font-weight:bold;">Request a Quote</a></td></tr></table>
            <p style="font-size:14px;line-height:1.5;color:#64748b;margin:0 0 20px;">Final pricing requires project review. Promotion is for new clients and new approved projects.</p>
          </td></tr>
          <tr><td style="padding:18px 30px 28px;border-top:1px solid #d5dde3;">
            <p style="font-size:15px;line-height:1.5;margin:0;color:#334155;">Best,<br>Roberts Landscape</p>
            <p style="font-size:12px;line-height:1.5;color:#64748b;margin:18px 0 0;">If this is not relevant, reply STOP and we will not follow up.</p>
          </td></tr>
        </table>
      </td></tr>
    </table>
  </body>
</html>"""

        if category == "hospitality":
            return f"""<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#f5f3ee;font-family:Arial,Helvetica,sans-serif;color:#1f2933;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f5f3ee;padding:24px 0;">
      <tr><td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:620px;background:#fff;border:1px solid #e0dbd0;">
          <tr><td style="padding:28px 30px 12px;">
            <div style="font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:#64748b;">Cape Cod Outdoor Upgrades</div>
            <h1 style="font-size:27px;line-height:1.2;margin:10px 0;color:#172033;">First impressions start outside</h1>
            <p style="font-size:16px;line-height:1.55;color:#334155;margin:0;">{safe_name} helps hospitality properties with patios, entrance walkways, plantings, drainage, and stonework that holds up in coastal weather.</p>
          </td></tr>
          <tr><td style="padding:8px 30px 4px;">
            <p style="font-size:16px;line-height:1.6;margin:0 0 14px;">Hi there,</p>
            <p style="font-size:16px;line-height:1.6;margin:0 0 14px;">If you are planning outdoor improvements at your property, we can walk the space and give you a practical next step — no hard sell.</p>
            <p style="font-size:16px;line-height:1.6;margin:0 0 18px;">For new clients, we are offering <strong>{discount}% off</strong> a new approved project.</p>
            <table role="presentation" cellspacing="0" cellpadding="0" style="margin:22px 0;"><tr><td style="background:#256f46;padding:13px 18px;"><a href="{url}" style="color:#fff;text-decoration:none;font-size:16px;font-weight:bold;">Request a Quote</a></td></tr></table>
            <p style="font-size:14px;line-height:1.5;color:#64748b;margin:0 0 20px;">Final pricing requires project review. Promotion is for new clients and new approved projects.</p>
          </td></tr>
          <tr><td style="padding:18px 30px 28px;border-top:1px solid #e0dbd0;">
            <p style="font-size:15px;line-height:1.5;margin:0;color:#334155;">Best,<br>Roberts Landscape</p>
            <p style="font-size:12px;line-height:1.5;color:#64748b;margin:18px 0 0;">If this is not relevant, reply STOP and we will not follow up.</p>
          </td></tr>
        </table>
      </td></tr>
    </table>
  </body>
</html>"""

        return f"""<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#f6f4ef;font-family:Arial,Helvetica,sans-serif;color:#1f2933;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f6f4ef;padding:24px 0;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:620px;background:#ffffff;border:1px solid #e4dfd4;">
            <tr>
              <td style="padding:28px 30px 14px 30px;">
                <div style="font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:#64748b;">Cape Cod Landscape Offer</div>
                <h1 style="margin:10px 0 8px 0;font-size:28px;line-height:1.2;color:#172033;">{discount}% off a new landscape project</h1>
                <p style="margin:0;font-size:16px;line-height:1.55;color:#334155;">For new customers planning patios, walkways, drainage, planting, stonework, or outdoor living upgrades.</p>
              </td>
            </tr>
            <tr>
              <td style="padding:8px 30px 4px 30px;">
                <p style="font-size:16px;line-height:1.6;margin:0 0 14px 0;">Hi there,</p>
                <p style="font-size:16px;line-height:1.6;margin:0 0 14px 0;">This is {escape(business_name)}. If you are thinking about a new landscape project on Cape Cod, now is a good time to get it on the calendar.</p>
                <p style="font-size:16px;line-height:1.6;margin:0 0 18px 0;">We will take a practical look at your space, talk through what will hold up in local weather, and give you a clear next step without the hard sell.</p>
                <table role="presentation" cellspacing="0" cellpadding="0" style="margin:22px 0;">
                  <tr>
                    <td style="background:#256f46;padding:13px 18px;">
                      <a href="{url}" style="color:#ffffff;text-decoration:none;font-size:16px;font-weight:bold;">Request a Quote</a>
                    </td>
                  </tr>
                </table>
                <p style="font-size:14px;line-height:1.5;color:#64748b;margin:0 0 20px 0;">Final pricing requires project review. Promotion is for new customers and new projects.</p>
              </td>
            </tr>
            <tr>
              <td style="padding:18px 30px 28px 30px;border-top:1px solid #e4dfd4;">
                <p style="font-size:15px;line-height:1.5;margin:0;color:#334155;">Best,<br>Roberts Landscape</p>
                <p style="font-size:12px;line-height:1.5;color:#64748b;margin:18px 0 0 0;">If this is not relevant, reply STOP and we will not follow up.</p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""
