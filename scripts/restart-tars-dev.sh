#!/bin/bash
# Restart TARS dev backend (8000) then frontend (5173). Backend starts without reload to avoid OOM.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORTS="8000 5173 5174 5175 5176 5177 5178 5179 5180 5181 5182 5183 5184 5185"
KILLED=""
for PORT in $PORTS; do
  while true; do
    PIDS=$(lsof -ti :$PORT 2>/dev/null || true)
    [ -z "$PIDS" ] && break
    for PID in $PIDS; do
      kill -9 "$PID" 2>/dev/null && KILLED="$KILLED $PID(port$PORT)"
    done
    sleep 0.2
  done
done
echo "Killed:${KILLED:- none}"
if lsof -iTCP:8000,5173 -sTCP:LISTEN 2>/dev/null; then echo "Ports still in use"; exit 1; fi
echo "Ports 8000,5173 free"

cd "$ROOT/backend"
export TARS_RELOAD=0
nohup .venv/bin/python -m tars.main > nohup-backend.log 2>&1 &
BACK_PID=$!
echo "Backend starting (pid $BACK_PID, no reload)..."
for i in $(seq 1 90); do
  code=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/docs 2>/dev/null || echo 000)
  if [ "$code" = "200" ]; then
    echo "Backend ready (HTTP $code)"
    break
  fi
  if [ "$i" -eq 90 ]; then
    echo "Backend failed to start; tail nohup-backend.log:"
    tail -30 nohup-backend.log
    exit 1
  fi
  sleep 1
done

cd "$ROOT/frontend"
nohup npm run dev -- --host 0.0.0.0 --port 5173 --strictPort > nohup-frontend.log 2>&1 &
FRONT_PID=$!
echo "Frontend starting (pid $FRONT_PID)..."
for i in $(seq 1 60); do
  code=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:5173/ 2>/dev/null || echo 000)
  if [ "$code" = "200" ]; then
    echo "Frontend ready (HTTP $code)"
    break
  fi
  if [ "$i" -eq 60 ]; then
    echo "Frontend failed to start; tail nohup-frontend.log:"
    tail -20 nohup-frontend.log
    exit 1
  fi
  sleep 1
done

echo "BACKEND_PID=$BACK_PID FRONTEND_PID=$FRONT_PID"
curl -s -o /dev/null -w 'backend:%{http_code} ' http://127.0.0.1:8000/docs
curl -s -o /dev/null -w 'frontend:%{http_code}\n' http://127.0.0.1:5173/
echo "Open http://localhost:5173/"
