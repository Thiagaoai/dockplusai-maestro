#!/usr/bin/env bash
# First-time VPS setup for MAESTRO.
# Run once as root on 2.24.215.132:
#   curl -fsSL <url>/vps_first_setup.sh | bash
set -euo pipefail

echo "=== MAESTRO VPS Setup ==="

# Docker
if ! command -v docker &>/dev/null; then
    apt-get update -q
    apt-get install -y ca-certificates curl gnupg
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
        https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
        | tee /etc/apt/sources.list.d/docker.list
    apt-get update -q
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
    echo "Docker instalado."
else
    echo "Docker já instalado."
fi

# App directory
mkdir -p /opt/maestro
echo "Diretório /opt/maestro criado."

# .env placeholder
if [ ! -f /opt/maestro/.env ]; then
    cat > /opt/maestro/.env <<'EOF'
# Copie o conteúdo do .env local e mude:
APP_ENV=production
DRY_RUN=false
WEBHOOK_BASE_URL=https://maestro.dockplusai.io
REDIS_URL=redis://redis:6379/0
STORAGE_BACKEND=supabase
EOF
    echo "ATENÇÃO: edite /opt/maestro/.env com as credenciais reais antes de fazer deploy."
else
    echo ".env já existe — não sobrescrito."
fi

# docker-compose.yml
if [ ! -f /opt/maestro/docker-compose.yml ]; then
    echo "ATENÇÃO: copie o docker-compose.yml do repo para /opt/maestro/docker-compose.yml"
fi

# Firewall
if command -v ufw &>/dev/null; then
    ufw allow 22/tcp
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw --force enable
    echo "UFW configurado (22, 80, 443)."
fi

echo ""
echo "=== Setup concluído ==="
echo "Próximos passos:"
echo "  1. Editar /opt/maestro/.env com todas as credenciais"
echo "  2. Rodar scripts/setup_cloudflare_tunnel.sh (configura tunnel + fecha portas 80/443)"
echo "  3. Push para main → CI/CD faz o deploy automático"
echo ""
echo "  IP deste VPS: $(curl -s ifconfig.me)"
echo "  ATENÇÃO: não expor este IP publicamente — use apenas Cloudflare Tunnel"
