#!/usr/bin/env bash
# TARS v5.0.3 — Docker Compose startup with pre-flight checks
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DEPLOY_DIR="$PROJECT_ROOT/deploy"

ENV_FILE="$DEPLOY_DIR/.env"

echo "=== TARS Docker Startup ==="
echo ""

# ── Pre-flight checks ────────────────────────────────────────────────

if ! command -v docker &>/dev/null; then
    echo "ERROR: docker not found. Install Docker Engine 24+."
    exit 1
fi

if ! docker compose version &>/dev/null; then
    echo "ERROR: docker compose not found. Install Docker Compose v2+."
    exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
    echo "Creating $ENV_FILE from .env.example ..."
    cp "$DEPLOY_DIR/.env.example" "$ENV_FILE"
    echo ""
    echo "⚠️  Please edit $ENV_FILE before starting:"
    echo "   - Set TARS_JWT_SECRET to a random string (openssl rand -hex 32)"
    echo "   - Configure your LLM provider (OLLAMA / DEEPSEEK_API_KEY)"
    echo "   - Change PG_PASSWORD if deploying outside localhost"
    echo ""
    echo "Then re-run this script."
    exit 0
fi

# Warn about default JWT secret
if grep -q "change-me-in-production" "$ENV_FILE" 2>/dev/null; then
    echo "⚠️  WARNING: TARS_JWT_SECRET is still the default value!"
    echo "   Generate one with: openssl rand -hex 32"
    echo ""
fi

# Check for host.docker.internal on Linux
if [ "$(uname -s)" = "Linux" ] && grep -q "host.docker.internal" "$ENV_FILE" 2>/dev/null; then
    echo "ℹ️  Linux detected — host.docker.internal requires extra_hosts or --add-host."
    echo "   The compose file includes 'extra_hosts' for the backend service."
    echo ""
fi

# ── Start services ────────────────────────────────────────────────────

COMPOSE_FILES=(-f "$DEPLOY_DIR/docker-compose.yml")

if [ -f "$DEPLOY_DIR/docker-compose.prod.yml" ]; then
    COMPOSE_FILES+=(-f "$DEPLOY_DIR/docker-compose.prod.yml")
fi

cd "$PROJECT_ROOT"

echo "Starting services..."
docker compose "${COMPOSE_FILES[@]}" up -d --build "$@"

echo ""
echo "Waiting for services to become healthy..."
sleep 3

# Show status
docker compose -f "$DEPLOY_DIR/docker-compose.yml" ps

echo ""
echo "=== TARS is starting ==="
echo "  Frontend: http://localhost:${TARS_FRONTEND_PORT:-8080}"
echo "  Backend:  http://localhost:${TARS_BACKEND_PORT:-8000}"
echo "  API Docs: http://localhost:${TARS_BACKEND_PORT:-8000}/docs"
echo ""
echo "First login: admin / Admin123! (change in Settings after login)"
echo "Logs: docker compose -f deploy/docker-compose.yml logs -f"
