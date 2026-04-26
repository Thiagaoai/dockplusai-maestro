#!/usr/bin/env bash
# Cloudflare Tunnel setup for MAESTRO (run on VPS as root).
# Hides VPS IP completely — no ports 80/443 exposed.
#
# Pre-requisites:
#   1. Domain dockplusai.io must be on Cloudflare (any plan, including Free)
#   2. You ran vps_first_setup.sh first
#
# Steps covered here:
#   A. Install cloudflared on VPS
#   B. Authenticate cloudflared with your Cloudflare account
#   C. Create the tunnel and DNS route
#   D. Write the tunnel config file
#   E. Get the tunnel token and add to .env
#   F. Lock down UFW — close 80/443, keep only 22 (SSH)
set -euo pipefail

DOMAIN="maestro.dockplusai.io"
TUNNEL_NAME="maestro"
APP_PORT="8000"

echo ""
echo "=== MAESTRO — Cloudflare Tunnel Setup ==="
echo "Domain:  $DOMAIN"
echo "Tunnel:  $TUNNEL_NAME"
echo ""

# ─────────────────────────────────────────────
# A. Install cloudflared
# ─────────────────────────────────────────────
if ! command -v cloudflared &>/dev/null; then
    echo "[1/6] Instalando cloudflared..."
    curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg \
        | gpg --dearmor -o /usr/share/keyrings/cloudflare-archive-keyring.gpg
    echo 'deb [signed-by=/usr/share/keyrings/cloudflare-archive-keyring.gpg] \
https://pkg.cloudflare.com/cloudflared any main' \
        > /etc/apt/sources.list.d/cloudflared.list
    apt-get update -q
    apt-get install -y cloudflared
    echo "    cloudflared instalado: $(cloudflared --version)"
else
    echo "[1/6] cloudflared já instalado: $(cloudflared --version)"
fi

# ─────────────────────────────────────────────
# B. Authenticate (opens browser — do once)
# ─────────────────────────────────────────────
if [ ! -f ~/.cloudflared/cert.pem ]; then
    echo ""
    echo "[2/6] Autenticando com Cloudflare..."
    echo "    Isso vai abrir um link. Copie e abra no seu navegador."
    echo "    Selecione o domínio dockplusai.io."
    echo ""
    cloudflared tunnel login
else
    echo "[2/6] Já autenticado com Cloudflare."
fi

# ─────────────────────────────────────────────
# C. Create tunnel + DNS route
# ─────────────────────────────────────────────
EXISTING=$(cloudflared tunnel list 2>/dev/null | grep "$TUNNEL_NAME" || true)
if [ -z "$EXISTING" ]; then
    echo ""
    echo "[3/6] Criando tunnel '$TUNNEL_NAME'..."
    cloudflared tunnel create "$TUNNEL_NAME"
else
    echo "[3/6] Tunnel '$TUNNEL_NAME' já existe."
fi

echo ""
echo "[4/6] Criando rota DNS: $DOMAIN → tunnel..."
cloudflared tunnel route dns "$TUNNEL_NAME" "$DOMAIN" || \
    echo "    DNS já configurado (ignorado)."

# ─────────────────────────────────────────────
# D. Write config file
# ─────────────────────────────────────────────
mkdir -p ~/.cloudflared

CRED_FILE=$(cloudflared tunnel info "$TUNNEL_NAME" 2>/dev/null \
    | grep -o '/root/.cloudflared/[a-z0-9-]*.json' || true)

if [ -z "$CRED_FILE" ]; then
    # Fallback: find the credentials file
    TUNNEL_ID=$(cloudflared tunnel info "$TUNNEL_NAME" 2>/dev/null | grep 'ID:' | awk '{print $2}' || true)
    CRED_FILE="/root/.cloudflared/${TUNNEL_ID}.json"
fi

cat > ~/.cloudflared/config.yml <<EOF
tunnel: ${TUNNEL_NAME}
credentials-file: ${CRED_FILE}

ingress:
  - hostname: ${DOMAIN}
    service: http://localhost:${APP_PORT}
    originRequest:
      connectTimeout: 30s
      noTLSVerify: false
  - service: http_status:404
EOF

echo "[5/6] Config gravada em ~/.cloudflared/config.yml"

# ─────────────────────────────────────────────
# E. Get token for Docker usage
# ─────────────────────────────────────────────
echo ""
echo "========================================================"
echo "  PRÓXIMO PASSO OBRIGATÓRIO:"
echo ""
echo "  Execute o comando abaixo para obter o TUNNEL_TOKEN:"
echo ""
echo "    cloudflared tunnel token $TUNNEL_NAME"
echo ""
echo "  Copie o token e adicione ao /opt/maestro/.env:"
echo ""
echo "    CLOUDFLARE_TUNNEL_TOKEN=eyJh..."
echo "    REDIS_URL=redis://default:SUA_SENHA@redis:6379/0"
echo "    REDIS_PASSWORD=SUA_SENHA_FORTE_AQUI"
echo ""
echo "========================================================"

# ─────────────────────────────────────────────
# F. Fechar portas 80 e 443 no firewall
#    (cloudflared usa só saída na 443 — entrada não é necessária)
# ─────────────────────────────────────────────
echo ""
echo "[6/6] Restringindo firewall (UFW)..."
if command -v ufw &>/dev/null; then
    ufw delete allow 80/tcp  2>/dev/null || true
    ufw delete allow 443/tcp 2>/dev/null || true
    ufw allow 22/tcp
    ufw --force enable
    echo "    UFW: somente porta 22 (SSH) aberta."
    echo "    Cloudflare Tunnel usa saída — sem necessidade de portas de entrada."
    ufw status
fi

echo ""
echo "=== Setup concluído ==="
echo ""
echo "Depois de adicionar o CLOUDFLARE_TUNNEL_TOKEN no .env, rode:"
echo "  cd /opt/maestro && docker compose pull && docker compose up -d --build"
echo ""
echo "Verifique o tunnel:"
echo "  docker compose logs cloudflared"
echo "  curl https://$DOMAIN/health"
echo ""
