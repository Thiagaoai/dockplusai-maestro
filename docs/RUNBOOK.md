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
