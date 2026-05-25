#!/usr/bin/env bash
# InsightForge INS-2.1 profile perf acceptance (manual / demo)
set -euo pipefail

PERF_THRESHOLD_MS=${PERF_THRESHOLD_MS:-60000}
BASE_URL=${BASE_URL:-http://127.0.0.1:8000}
API_KEY=${TARS_ADMIN_API_KEY:-}

echo "[acceptance] INS-2.1 profile perf — threshold ${PERF_THRESHOLD_MS}ms"

if [[ -z "${API_KEY}" ]]; then
  echo "Set TARS_ADMIN_API_KEY for authenticated /api/insight calls" >&2
  exit 1
fi

ver=$(curl -sf -H "X-API-Key: ${API_KEY}" "${BASE_URL}/api/insight/version" | jq -r .version)
echo "InsightForge version: ${ver}"
[[ "${ver}" == "INS-2.1.0" ]] || echo "WARN: expected INS-2.1.0, got ${ver}"

echo "Run forge against demo datasource and assert perf.total_ms — wire datasource_id as \$1"
DS_ID=${1:-}
if [[ -z "${DS_ID}" ]]; then
  echo "Usage: $0 <datasource_id>" >&2
  exit 1
fi

run_id=$(curl -sf -X POST \
  -H "X-API-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  "${BASE_URL}/api/insight/datasources/${DS_ID}/profile/start" \
  -d '{}' | jq -r .run_id)

echo "Started run ${run_id}, polling..."
for _ in $(seq 1 120); do
  status=$(curl -sf -H "X-API-Key: ${API_KEY}" \
    "${BASE_URL}/api/insight/runs/${run_id}" | jq -r .status)
  if [[ "${status}" == "completed" || "${status}" == "failed" ]]; then
    break
  fi
  sleep 2
done

total_ms=$(curl -sf -H "X-API-Key: ${API_KEY}" \
  "${BASE_URL}/api/insight/runs/${run_id}" | jq '.insight_snapshot.perf.total_ms // empty')

if [[ -z "${total_ms}" ]]; then
  echo "FAIL: insight_snapshot.perf.total_ms missing" >&2
  exit 1
fi

echo "perf.total_ms=${total_ms}"
if (( total_ms > PERF_THRESHOLD_MS )); then
  echo "FAIL: ${total_ms}ms > ${PERF_THRESHOLD_MS}ms threshold" >&2
  exit 1
fi

echo "PASS: profile perf within threshold"
