#!/usr/bin/env bash
# Manual deploy to VPS. Same steps as CI/CD but run locally.
# Requires: VPS_HOST, VPS_USER, VPS_SSH_KEY_PATH env vars or defaults below.
set -euo pipefail

VPS_HOST="${VPS_HOST:-2.24.215.132}"
VPS_USER="${VPS_USER:-root}"
VPS_SSH_KEY="${VPS_SSH_KEY_PATH:-$HOME/.ssh/id_rsa}"
IMAGE="ghcr.io/thiagaoai/dockplusai-maestro:latest"

echo "=== Deploy manual para $VPS_HOST ==="

# Copy compose file
echo "→ Copiando docker-compose.yml..."
scp -i "$VPS_SSH_KEY" -o StrictHostKeyChecking=no \
    docker-compose.yml "$VPS_USER@$VPS_HOST:/opt/maestro/docker-compose.yml"

# Run on VPS
echo "→ Executando no VPS..."
ssh -i "$VPS_SSH_KEY" -o StrictHostKeyChecking=no "$VPS_USER@$VPS_HOST" bash <<EOF
set -e
cd /opt/maestro
docker pull $IMAGE
docker compose up -d --remove-orphans
docker compose ps
echo "Deploy concluido: \$(date -u)"
EOF

echo ""
echo "✅ Deploy concluído."
echo "Verificando saúde: https://maestro.dockplusai.io/health"
