from maestro.config import Settings
from maestro.profiles._schema import BusinessProfile
from maestro.schemas.events import AgentResult, AgentRunRecord, ApprovalRequest
from maestro.subagents.cfo import (
    analyze_margin,
    forecast_cashflow,
    recommend_financial_actions,
    reconcile_invoices,
)


class CFOAgent:
    def __init__(self, settings: Settings, profile: BusinessProfile) -> None:
        self.settings = settings
        self.profile = profile

    async def run(self, question: str = "weekly financial briefing") -> tuple[AgentResult, AgentRunRecord]:
        reconciliation = reconcile_invoices(self.profile.business_id)
        margin = analyze_margin(self.profile)
        cashflow = forecast_cashflow(margin["estimated_revenue_usd"])

        # Determine if any financial action requires HITL approval
        action_plan = recommend_financial_actions(
            self.profile, margin, cashflow, reconciliation
        )

        data = {
            "question": question,
            "reconciliation": reconciliation,
            "margin": margin,
            "cashflow": cashflow,
            "recommended_actions": action_plan,
            "sources": reconciliation["sources"] + margin["sources"] + cashflow["sources"],
        }

        message = (
            f"CFO {self.profile.business_name}: estimated gross margin "
            f"{margin['estimated_gross_margin_pct']}%. "
            f"{len(action_plan['actions'])} action(s) recommended."
        )

        approval = None
        if action_plan["requires_approval"]:
            approval = ApprovalRequest(
                business=self.profile.business_id,
                event_id=f"cfo:{self.profile.business_id}:actions",
                action="cfo_financial_actions_dry_run",
                preview={
                    "actions": action_plan["actions"],
                    "max_impact_usd": action_plan["max_impact_usd"],
                    "threshold_usd": action_plan["threshold_usd"],
                    "dry_run": self.settings.dry_run,
                    "profit_signal": "margin",
                },
            )

        result = AgentResult(
            business=self.profile.business_id,
            agent_name="cfo",
            message=message,
            data=data,
            approval=approval,
            profit_signal="margin",
        )
        run = AgentRunRecord(
            business=self.profile.business_id,
            agent_name="cfo",
            input=question,
            output=result.model_dump_json(),
            profit_signal="margin",
            prompt_version=self.settings.prompt_version,
            dry_run=self.settings.dry_run,
        )
        return result, run
