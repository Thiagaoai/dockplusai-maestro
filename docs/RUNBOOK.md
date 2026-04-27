# MAESTRO Runbook

## Emergency Stop

Send `/stop` to the Telegram bot. Webhooks continue to receive events, but agents skip execution.

Resume with `/start`.

## Health Check

```bash
curl http://localhost:8000/health
```

Expected:

```json
{"status":"ok","app":"MAESTRO","env":"dev","dry_run":true}
```

## Rollback

Production target:

```bash
ssh thiago@vps "cd /opt/maestro && git checkout <previous_tag> && docker compose up -d --build"
```

## First Incident Checks

- Is `/health` returning OK?
- Is `DRY_RUN=true` during testing?
- Did `/stop` pause agents?
- Are webhook secrets matching `.env`?
- Is the event duplicated in `processed_events`?
- Did `audit_log` record the decision/action?

## Production Dry-Run Smoke

Use this before enabling any new real automation:

```bash
APP_ENV=production DRY_RUN=true STORAGE_BACKEND=supabase \
LANGCHAIN_TRACING_V2=true LANGCHAIN_PROJECT=maestro-prod \
.venv/bin/python scripts/smoke_langsmith_trace.py
```

Confirm the printed agent run has `prompt_version`, `tokens_in`, `tokens_out`, `cost_usd`, and `langsmith_trace_url`. External actions must remain dry-run or wait for Telegram approval.

Last verified smoke:

- Date: 2026-04-26
- Project: `maestro-prod`
- Agent: `cfo`
- Run ID: `31a07c78-2ca1-420b-8c48-bb49beb500f0`
- Usage: `tokens_in=1113`, `tokens_out=767`, `cost_usd=0.014844`
- Supabase persisted: yes
- Dry-run: yes

## Production Dry-Run Soak

Run controlled soak checks with:

```bash
APP_ENV=production DRY_RUN=true STORAGE_BACKEND=supabase \
LANGCHAIN_TRACING_V2=true LANGCHAIN_PROJECT=maestro-prod \
.venv/bin/python scripts/soak_production_dry_run.py --cycles 2 --agents cfo --business roberts --interval-seconds 1
```

Each iteration verifies `agent_runs`, `business_metrics`, `audit_log`, LangSmith URL, token usage, cost, and `dry_run=true`.

Last verified soak:

- Date: 2026-04-26
- Project: `maestro-prod`
- Agent: `cfo`
- Runs: `07a25b2b-f14b-4206-a74f-6bd25f9d03f7`, `3083530f-b480-49f8-b31b-b57052089c94`
- Each run: `tokens_in=1113`, `tokens_out=768`, `cost_usd=0.014859`
- Supabase persisted: yes
- Business metrics persisted: yes
- Audit log persisted: yes
- Dry-run: yes
