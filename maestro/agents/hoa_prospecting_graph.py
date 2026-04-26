from __future__ import annotations

from typing import Any, TypedDict
from uuid import NAMESPACE_URL, uuid5

from langgraph.graph import END, StateGraph

from maestro.config import Settings, get_settings
from maestro.repositories import store
from maestro.schemas.events import LeadRecord
from maestro.services.prospecting import prospect_queue_item
from maestro.services.resend import ResendEmailClient
from maestro.services.telegram import TelegramService


class HOAProspectingState(TypedDict, total=False):
    business: str
    campaign: str
    contacts: list[dict[str, Any]]
    prepared: list[dict[str, Any]]
    sent: list[dict[str, Any]]
    cc: list[str]
    dry_run: bool


VERIFIED_PROVINCETOWN_HOA_CONTACTS: list[dict[str, Any]] = [
    {
        "name": "Race Point Townhouse Condominiums",
        "email": "racepointcondos@gmail.com",
        "category": "condominium_association",
        "source_url": "https://www.racepointtownhouse.com/home",
        "verification": "Official Race Point Townhouse Condominiums site lists this email and Provincetown address.",
    },
    {
        "name": "Seashore Point-Deaconess Condominium Association - General Manager",
        "email": "dabel@thedartmouthgroup.com",
        "category": "condominium_association_manager",
        "source_url": "https://seashorepointresidents.com/property-manager",
        "verification": "Seashore Point residents site lists David Abel as General Manager for the association.",
    },
    {
        "name": "Seashore Point-Deaconess Condominium Association - Lead Concierge",
        "email": "cmeyers@thedartmouthgroup.com",
        "category": "condominium_association_manager",
        "source_url": "https://seashorepointresidents.com/property-manager",
        "verification": "Seashore Point residents site lists Charlotte Meyers as Lead Concierge.",
    },
    {
        "name": "Seashore Point-Deaconess Condominium Association - Portfolio Assistant",
        "email": "mlinskey@thedartmouthgroup.com",
        "category": "condominium_association_manager",
        "source_url": "https://seashorepointresidents.com/property-manager",
        "verification": "Seashore Point residents site lists Megan Linskey as Portfolio Assistant Supervisor.",
    },
    {
        "name": "Seashore Point-Deaconess Condominium Association - Hospitality Manager",
        "email": "cpierson-alter@thedartmouthgroup.com",
        "category": "condominium_association_manager",
        "source_url": "https://seashorepointresidents.com/property-manager",
        "verification": "Seashore Point residents site lists Chase Pierson-Alter as Hospitality Manager.",
    },
    {
        "name": "Peters Property Management",
        "email": "info@peterspropertymgt.com",
        "category": "condominium_property_manager",
        "source_url": "https://www.peterspropertymgt.com/team",
        "verification": "Peters site lists Provincetown address and property/condo management contact.",
    },
    {
        "name": "Peters Property Management - CEO",
        "email": "laurie@peterspropertymgt.com",
        "category": "condominium_property_manager",
        "source_url": "https://www.peterspropertymgt.com/team",
        "verification": "Peters team page lists Laurie Ferrari and her contact email.",
    },
    {
        "name": "Peters Property Management - Operations",
        "email": "susan@peterspropertymgt.com",
        "category": "condominium_property_manager",
        "source_url": "https://www.peterspropertymgt.com/team",
        "verification": "Peters team page lists Susan Denison and her contact email.",
    },
    {
        "name": "Peters Property Management - Condominium Financials",
        "email": "matt@peterspropertymgt.com",
        "category": "condominium_property_manager",
        "source_url": "https://www.peterspropertymgt.com/team",
        "verification": "Peters team page lists Matt Sukovich for condominium financials.",
    },
    {
        "name": "Tip of the Cape Property Services",
        "email": "info@tipofthecapeps.com",
        "category": "condominium_property_manager",
        "source_url": "https://tipofthecapeps.com/",
        "verification": "Tip of the Cape site says it manages condominium association units/complexes and lists this email.",
    },
]


def build_hoa_email(settings: Settings) -> dict[str, str]:
    url = settings.roberts_website_url
    subject = "Cape Cod landscape help for Provincetown condo communities"
    text = (
        "Hi,\n\n"
        "I am reaching out from Roberts Landscape on Cape Cod. We help local property owners "
        "and community properties with clean, practical landscape and hardscape work: patios, "
        "walkways, drainage, planting, stonework, and outdoor living upgrades.\n\n"
        f"For new association or property-management clients, we are offering {settings.roberts_promo_discount_percent}% off a new approved landscape project.\n\n"
        f"You can see our work and request a quote here: {url}\n\n"
        "If you are the right person to talk with about exterior projects or common-area improvements, "
        "I would be glad to take a look and give you a clear next step.\n\n"
        "Best,\nRoberts Landscape\n\n"
        "If this is not relevant, reply STOP and we will not follow up."
    )
    html = f"""<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#f7f7f4;font-family:Arial,Helvetica,sans-serif;color:#1f2933;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f7f7f4;padding:24px 0;">
      <tr><td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:620px;background:#fff;border:1px solid #dedbd2;">
          <tr><td style="padding:28px 30px 12px;">
            <div style="font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:#64748b;">Provincetown Condo & HOA Landscape Help</div>
            <h1 style="font-size:27px;line-height:1.2;margin:10px 0;color:#172033;">A practical landscape team for Cape Cod communities</h1>
            <p style="font-size:16px;line-height:1.55;color:#334155;margin:0;">Roberts Landscape helps with patios, walkways, drainage, planting, stonework, and outdoor living upgrades.</p>
          </td></tr>
          <tr><td style="padding:8px 30px 4px;">
            <p style="font-size:16px;line-height:1.6;margin:0 0 14px;">Hi,</p>
            <p style="font-size:16px;line-height:1.6;margin:0 0 14px;">I am reaching out from Roberts Landscape. If your association or managed property is planning exterior improvements, we can take a look and give you a clear next step.</p>
            <p style="font-size:16px;line-height:1.6;margin:0 0 18px;">For new association or property-management clients, we are offering <strong>{settings.roberts_promo_discount_percent}% off</strong> a new approved landscape project.</p>
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
    return {"subject": subject, "text": text, "html": html}


async def seed_contacts_node(state: HOAProspectingState) -> HOAProspectingState:
    business = state.get("business", "roberts")
    contacts = VERIFIED_PROVINCETOWN_HOA_CONTACTS[:10]
    prepared: list[dict[str, Any]] = []
    for contact in contacts:
        event_id = f"scrape:{business}:provincetown_hoa:{contact['email'].casefold()}"
        lead = LeadRecord(
            id=uuid5(NAMESPACE_URL, event_id),
            event_id=event_id,
            business=business,
            name=contact["name"],
            email=contact["email"],
            source="scrape_provincetown_hoa",
            message=contact["verification"],
            status="prospect_imported",
            raw=contact,
        )
        await store.upsert_lead(lead)
        queue_item = prospect_queue_item(
            business=business,
            lead=lead,
            source_name="provincetown_hoa_verified_web",
            source_ref=event_id,
            source_type="scrape",
        )
        queue_item["payload"] = {
            **queue_item["payload"],
            "property_name": contact["name"],
            "source_url": contact["source_url"],
            "verification_note": contact["verification"],
        }
        await store.upsert_prospect_queue_item(queue_item)
        prepared.append({"lead_id": str(lead.id), **contact})
    return {"contacts": contacts, "prepared": prepared}


async def send_emails_node(state: HOAProspectingState) -> HOAProspectingState:
    settings = get_settings()
    email = build_hoa_email(settings)
    client = ResendEmailClient(settings)
    sent: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    table_errors: list[dict[str, Any]] = []
    cc = state.get("cc") or []
    dry_run = state.get("dry_run", True)
    for contact in state.get("prepared", [])[:10]:
        if dry_run:
            sent.append({"to": contact["email"], "status": "dry_run"})
            continue
        try:
            result = await client.send_business_email(
                business="roberts",
                to=contact["email"],
                cc=cc,
                subject=email["subject"],
                body=email["text"],
                html=email["html"],
                idempotency_key=f"provincetown-hoa:{contact['email'].casefold()}",
            )
        except Exception as exc:
            failed.append({"to": contact["email"], "status": "failed", "error": str(exc)[:300]})
            continue
        sent_item = {
            "to": contact["email"],
            "status": result["status"],
            "email_id": result.get("email_id"),
            "property_name": contact["name"],
        }
        sent.append(sent_item)
        try:
            await store.upsert_clients_web_verified(
                {
                    "business": "roberts",
                    "lead_id": contact["lead_id"],
                    "property_name": contact["name"],
                    "email": contact["email"],
                    "source_name": "provincetown_hoa_verified_web",
                    "source_ref": f"scrape:roberts:provincetown_hoa:{contact['email'].casefold()}",
                    "source_url": contact["source_url"],
                    "verification_note": contact["verification"],
                    "campaign": state.get("campaign", "provincetown_hoa_web"),
                    "email_id": result.get("email_id"),
                    "send_status": "sent",
                    "payload": contact,
                }
            )
        except Exception as exc:
            table_errors.append(
                {
                    "email": contact["email"],
                    "table": "clients_web_verified",
                    "error": str(exc)[:300],
                }
            )
    if not dry_run:
        attempted_count = len(state.get("prepared", [])[:10])
        await TelegramService(settings).send_message(
            "Roberts web verified prospecting sent.\n"
            f"Attempted/Sent: {attempted_count}/{len(sent)}\n"
            f"Failed: {len(failed)}"
        )
    await store.add_audit_log(
        event_type="tool_call",
        business="roberts",
        agent="prospecting",
        action="provincetown_hoa_email_batch",
        payload={
            "attempted_count": len(state.get("prepared", [])[:10]),
            "sent_count": len(sent),
            "failed_count": len(failed),
            "table_error_count": len(table_errors),
            "dry_run": dry_run,
            "cc_count": len(cc),
        },
    )
    return {"sent": sent, "failed": failed, "table_errors": table_errors}


def build_provincetown_hoa_graph():
    graph = StateGraph(HOAProspectingState)
    graph.add_node("seed_verified_contacts", seed_contacts_node)
    graph.add_node("send_emails", send_emails_node)
    graph.set_entry_point("seed_verified_contacts")
    graph.add_edge("seed_verified_contacts", "send_emails")
    graph.add_edge("send_emails", END)
    return graph.compile()
