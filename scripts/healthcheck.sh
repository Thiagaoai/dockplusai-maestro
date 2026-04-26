#!/usr/bin/env bash
set -euo pipefail

curl -fsS "${WEBHOOK_BASE_URL:-http://localhost:8000}/health"
