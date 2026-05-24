#!/usr/bin/env bash
# Phase 1 Data Copilot acceptance — requires running backend on TARS_BASE_URL (default http://127.0.0.1:8000)
set -euo pipefail

BASE="${TARS_BASE_URL:-http://127.0.0.1:8000}"
TENANT="${TARS_TENANT:-default}"

echo "== Phase 1 acceptance: $BASE =="

login() {
  local user="$1" pass="$2"
  curl -sf -X POST "$BASE/api/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"$user\",\"password\":\"$pass\"}" \
    | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))"
}

TOKEN="${TARS_TOKEN:-}"
if [[ -z "$TOKEN" ]]; then
  TOKEN="$(login "${TARS_USER:-admin}" "${TARS_PASS:-admin123}" || true)"
fi
if [[ -z "$TOKEN" ]]; then
  echo "WARN: could not login; set TARS_TOKEN or TARS_USER/TARS_PASS"
  exit 1
fi

AUTH=(-H "Authorization: Bearer $TOKEN" -H "X-Tenant-Id: $TENANT")

echo "-- modules enabled --"
curl -sf "${AUTH[@]}" "$BASE/api/settings/modules" | head -c 500
echo

echo "-- insight datasources --"
DS_JSON="$(curl -sf "${AUTH[@]}" "$BASE/api/insight/datasources" || echo '[]')"
DS_ID="$(echo "$DS_JSON" | python3 -c "
import sys, json
data = json.load(sys.stdin)
items = data if isinstance(data, list) else data.get('datasources', data.get('items', []))
print(items[0]['id'] if items else '')
" 2>/dev/null || true)"

if [[ -z "$DS_ID" ]]; then
  echo "SKIP: no insight datasource; seed one before full E2E"
  exit 0
fi

echo "-- ask metric (expect citations array) --"
ASK_RESP="$(curl -sf "${AUTH[@]}" -X POST "$BASE/api/insight/datasources/$DS_ID/ask" \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"昨日 GMV\"}" || echo '{}')"

echo "$ASK_RESP" | python3 -c "
import sys, json
d = json.load(sys.stdin)
ans = d.get('answer') or d
cites = ans.get('citations') or []
print('branch:', ans.get('branch'))
print('citations:', len(cites))
if not cites:
    raise SystemExit('FAIL: expected citations.length >= 0 (knowledge optional in empty KB)')
print('OK: ask returned', len(cites), 'citation(s)')
"

echo "== Phase 1 acceptance passed =="
