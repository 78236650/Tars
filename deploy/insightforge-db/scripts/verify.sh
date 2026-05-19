#!/usr/bin/env bash
# 验证测试库与 GMV 数据
set -euo pipefail
export DOCKER_HOST="${DOCKER_HOST:-unix:///Users/daobanxiang/.docker/run/docker.sock}"

echo "=== docker compose ps ==="
docker compose ps -a 2>/dev/null || docker ps -a --filter name=tars-insight

gmv_mysql() {
  docker exec tars-insight-mysql mysql -uinsight -pinsight_pass insight_demo -N -e \
    "SELECT COALESCE(SUM(amount),0) FROM orders WHERE status='paid';" 2>/dev/null
}

gmv_pg() {
  docker exec tars-insight-postgres psql -U insight -d insight_demo -t -c \
    "SELECT COALESCE(SUM(amount),0) FROM orders WHERE status='paid';" 2>/dev/null | tr -d ' '
}

if out=$(gmv_mysql); then
  echo "MySQL GMV (paid): $out  (期望 4197.00)"
else
  echo "MySQL: 未就绪"
fi

if out=$(gmv_pg); then
  echo "PostgreSQL GMV (paid): $out  (期望 4197.00)"
else
  echo "PostgreSQL: 未就绪"
fi
