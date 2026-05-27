#!/usr/bin/env bash
# TARS v4.3.2 stable — build backend deps + frontend dist (bare-metal deploy helper)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> TARS v4.3.2 stable deploy prep"
echo "    Root: $ROOT"

if [[ ! -f backend/requirements.txt ]]; then
  echo "error: run from TARS repository root" >&2
  exit 1
fi

echo "==> Backend venv + dependencies"
cd backend
if [[ ! -d venv ]]; then
  python3 -m venv venv
fi
# shellcheck disable=SC1091
source venv/bin/activate
pip install -q -r requirements.txt
if [[ ! -f .env ]]; then
  cp -n .env.example .env 2>/dev/null || true
  echo "    Created backend/.env from example — please edit API keys"
fi
cd "$ROOT"

echo "==> Frontend production build"
cd frontend
if [[ -f package-lock.json ]]; then
  npm ci
else
  npm install
fi
npm run build
cd "$ROOT"

echo "==> Smoke tests (v4.3.2)"
cd backend
source venv/bin/activate
pytest tests/test_wiki_smoke_e2e.py tests/test_superpowers_v432_e2e.py -q --tb=no || {
  echo "warn: smoke tests failed — fix before production" >&2
}
cd "$ROOT"

echo ""
echo "==> Done. Start production backend:"
echo "    cd backend && source venv/bin/activate"
echo "    python3 -m uvicorn tars.main:app --host 0.0.0.0 --port 8000 --workers 1"
echo ""
echo "    Serve frontend/dist via Nginx, or:"
echo "    cd deploy && cp .env.example .env && docker compose up -d --build"
echo ""
echo "Docs: docs/guides/operations-manual.md"
echo "Checklist: docs/04-运维文档/v4.3.2-stable-release-checklist.md"
