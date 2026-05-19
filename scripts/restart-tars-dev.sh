#!/bin/bash
set -euo pipefail
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
cd /Users/daobanxiang/myproject/TARS/backend
nohup .venv/bin/python -m tars.main > nohup-backend.log 2>&1 &
BACK_PID=$!
for i in $(seq 1 60); do
  code=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/api/insight/version 2>/dev/null || echo 000)
  [ "$code" = "200" ] && break
  sleep 1
done
cd /Users/daobanxiang/myproject/TARS/frontend
nohup npm run dev -- --host 127.0.0.1 --port 5173 --strictPort > nohup-frontend.log 2>&1 &
FRONT_PID=$!
for i in $(seq 1 60); do
  code=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:5173/ 2>/dev/null || echo 000)
  [ "$code" = "200" ] && break
  sleep 1
done
echo "BACKEND_PID=$BACK_PID FRONTEND_PID=$FRONT_PID"
curl -s -o /dev/null -w 'backend:%{http_code}\n' http://127.0.0.1:8000/api/insight/version
curl -s -o /dev/null -w 'frontend:%{http_code}\n' http://127.0.0.1:5173/
