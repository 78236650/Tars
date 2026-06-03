#!/usr/bin/env bash
# TARS v5.0.3 — Docker build & optional push
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DEPLOY_DIR="$PROJECT_ROOT/deploy"

TAG="${TARS_DOCKER_TAG:-v5.0.3}"
REGISTRY="${TARS_DOCKER_REGISTRY:-}"  # e.g. "registry.example.com/tars"

cd "$PROJECT_ROOT"

echo "=== TARS Docker Build ==="
echo "  Tag:      $TAG"
echo "  Registry: ${REGISTRY:-<none, local only>}"
echo ""

echo "[1/2] Building backend image..."
docker compose -f "$DEPLOY_DIR/docker-compose.yml" build backend

echo "[2/2] Building frontend image..."
docker compose -f "$DEPLOY_DIR/docker-compose.yml" build frontend

if [ -n "$REGISTRY" ]; then
    echo ""
    echo "[3/4] Tagging images for registry..."
    docker tag tars-backend  "$REGISTRY/backend:$TAG"
    docker tag tars-frontend "$REGISTRY/frontend:$TAG"

    echo "[4/4] Pushing..."
    docker push "$REGISTRY/backend:$TAG"
    docker push "$REGISTRY/frontend:$TAG"

    echo ""
    echo "Pushed:"
    echo "  $REGISTRY/backend:$TAG"
    echo "  $REGISTRY/frontend:$TAG"
else
    echo ""
    echo "Built locally. Use TARS_DOCKER_REGISTRY=... to push."
fi

echo ""
echo "Done."
