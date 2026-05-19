#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker 未安装或未在 PATH 中"
  exit 1
fi

docker compose up -d

echo ""
echo "SearXNG: http://localhost:8888"
echo "JSON API: http://localhost:8888/search?q=test&format=json"
echo "TARS 环境变量: SEARXNG_URL=http://localhost:8888"
echo ""
docker compose ps
