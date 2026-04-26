from html import escape
from typing import Any
from uuid import uuid4

from maestro.config import Settings
from maestro.profiles import load_profile
from maestro.schemas.events import AgentRunRecord, ApprovalRequest
from maestro.services.prospecting import interleave_prospect_sources


class ProspectingAgent:
    def __init__(self, settings: Settings, store) -> None:
        self.settings = settings
        self.store = store

    async def prepare_roberts_batch(self, batch_size: int | None = None) -> tuple[ApprovalRequest | None, AgentRunRecord]:
        business = "roberts"
        size = batch_size or self.settings.prospecting_batch_size_roberts
        owned_target = max(size, self.settings.prospecting_customer_per_scrape_cycle * size)
        scrape_target = max(size, self.settings.prospecting_scrape_per_cycle * size)
        owned = await self.store.list_prospect_queue(
            business, status="queued", limit=owned_target, source_type="customer_file"
        )
        scrape = await self.store.list_prospect_queue(
            business, status="queued", limit=scrape_target, source_type="scrape"
        )
        selected = interleave_prospect_sources(
            owned,
            scrape,
            owned_per_cycle=self.settings.prospecting_customer_per_scrape_cycle,
            scrape_per_cycle=self.settings.prospecting_scrape_per_cycle,
        )[:size]

        if not selected:
            run = AgentRunRecord(
                business=business,
                agent_name="prospecting",
                input="prepare_roberts_batch",
                output='{"status":"empty"}',
                profit_signal="pipeline",
                prompt_version=self.settings.prompt_version,
                dry_run=self.settings.dry_run,
            )
            return None, run

        profile = load_profile(business)
        subject = "10% off a new landscape project on Cape Cod"
        text_body = self._text_body(profile.business_name)
        html_body = self._html_body(profile.business_name)
        prospects = [self._prospect_preview(item) for item in selected]
        source_refs = [item["source_ref"] for item in selected]
        preview = {
            "campaign": {
                "name": "Roberts 10% New Customer Landscape Promo",
                "business": business,
                "batch_size": len(selected),
                "schedule": "08:00, 11:00, 15:00, 17:00 America/New_York",
                "offer": f"{self.settings.roberts_promo_discount_percent}% off for new customers",
                "cta_url": self.settings.roberts_website_url,
                "tone": "natural American sales tone for Cape Cod, MA homeowners",
            },
            "email": {
                "subject": subject,
                "text": text_body,
                "html": html_body,
            },
            "prospects": prospects,
            "source_refs": source_refs,
            "dry_run": self.settings.dry_run,
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
            input=f"prepare batch size={size}",
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
            "source_ref": item.get("source_ref"),
            "lead_id": item.get("lead_id"),
            "name": payload.get("lead_name"),
            "has_email": payload.get("has_email", False),
            "has_phone": payload.get("has_phone", False),
        }

    def _text_body(self, business_name: str) -> str:
        discount = self.settings.roberts_promo_discount_percent
        url = self.settings.roberts_website_url
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

    def _html_body(self, business_name: str) -> str:
        discount = self.settings.roberts_promo_discount_percent
        url = escape(self.settings.roberts_website_url)
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
