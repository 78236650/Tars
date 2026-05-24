#!/usr/bin/env bash
# Phase 3 OpenClaw acceptance — unit/integration tests (v4.3.0)
# Spec §7.1 regression checklist (automated portions)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND="$ROOT/backend"
VENV="$BACKEND/.venv/bin/python"

if [[ ! -x "$VENV" ]]; then
  VENV="python3"
fi

echo "== Phase 3 OpenClaw acceptance (pytest) =="

cd "$BACKEND"

echo "-- §7.1 #6 ChannelRouter tests (>=5 cases) --"
$VENV -m pytest tests/test_channel_router.py -q

echo "-- §7.1 #2-3 Cron delegate + prompt --"
$VENV -m pytest tests/test_cron_delegate_prompt.py tests/unit/test_cron_runtime.py -q

echo "-- §7.1 #4 Tool approval --"
$VENV -m pytest tests/test_tool_approval.py -q

echo "-- §7.1 #5 Subagent handoff --"
$VENV -m pytest tests/test_subagent_handoff.py -q

echo "-- §7.2 Follow-up queue --"
$VENV -m pytest tests/test_follow_up_queue.py -q

echo "-- WebSocket routing regression --"
$VENV -m pytest tests/unit/test_websocket_routing.py tests/unit/test_tenant_websocket.py \
  tests/test_evolution_websocket_feedback.py -q

echo "-- Frontend ApprovalDialog + QueueStatus --"
if [[ -f "$ROOT/frontend/package.json" ]]; then
  (cd "$ROOT/frontend" && npm run test:unit -- --run \
    src/components/chat/ApprovalDialog.spec.ts \
    src/components/chat/QueueStatus.spec.ts)
fi

echo ""
echo "== Phase 3 automated acceptance passed =="
echo ""
echo "Manual §7.1 checks (not automated here):"
echo "  1. Chat WebSocket E2E: streaming, tools, Insight strip"
echo "  4. shell/command approval dialog in browser (approve + deny paths)"
echo "  5. /subagent handoff UI accept (WS subagent_handoff_action or REST /api/handoffs)"
