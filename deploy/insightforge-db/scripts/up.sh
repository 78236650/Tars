#!/usr/bin/env bash
# 启动 InsightForge 测试库（自动 fallback）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

export DOCKER_HOST="${DOCKER_HOST:-unix:///Users/daobanxiang/.docker/run/docker.sock}"

log() { echo "[insight-db] $*"; }

docker_ok() {
  docker info >/dev/null 2>&1
}

wait_healthy() {
  local name="$1"
  local max="${2:-60}"
  for i in $(seq 1 "$max"); do
    local st
    st=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$name" 2>/dev/null || echo "missing")
    if [[ "$st" == "healthy" || "$st" == "running" ]]; then
      log "${name} 就绪 (${st})"
      return 0
    fi
    sleep 2
  done
  log "警告: ${name} 未在预期时间内 healthy (最后状态: ${st})"
  return 1
}

if ! docker_ok; then
  log "docker CLI 不可用（Cursor 内置终端常见 permission denied）"
  if [[ -S "${DOCKER_HOST#unix://}" ]] || [[ -S "/Users/daobanxiang/.docker/run/docker.sock" ]]; then
    log "改用 Docker API (curl) 启动 mysql / postgres / doris ..."
    bash "${ROOT}/scripts/curl-docker.sh" up-mysql-postgres-doris
    bash "${ROOT}/scripts/seed-doris.sh" || log "Doris 灌数稍后重试: bash scripts/seed-doris.sh"
    echo ""
    cat "${ROOT}/connections.env" 2>/dev/null || true
    exit 0
  fi
  log "请先打开 Docker Desktop，然后在 系统终端.app 执行:"
  log "  cd ${ROOT} && ./scripts/up.sh"
  exit 1
fi

log "使用 docker compose 启动 ..."
docker compose pull mysql postgres 2>/dev/null || true

# 先启动轻量库（不含 mysql — 若已有 MySQL 见 EXISTING-MYSQL.md）
docker compose up -d postgres
wait_healthy tars-insight-postgres 45 || docker logs tars-insight-postgres --tail 30

if [[ "${START_BUNDLED_MYSQL:-0}" == "1" ]]; then
  docker compose --profile bundled up -d mysql
  wait_healthy tars-insight-mysql 45 || docker logs tars-insight-mysql --tail 30
else
  log "跳过 bundled MySQL（默认使用已有 MySQL；要额外起一个: START_BUNDLED_MYSQL=1 ./scripts/up.sh）"
fi

# Doris（可选，失败不阻塞）
if docker compose up -d doris; then
  bash "${ROOT}/scripts/seed-doris.sh" || log "Doris 灌数失败，见: docker logs tars-insight-doris --tail 50"
else
  log "Doris 启动跳过（可稍后: docker compose up -d doris）"
fi

# Oracle（可选，ARM Mac 较慢）
if [[ "${SKIP_ORACLE:-}" != "1" ]]; then
  log "启动 Oracle（首次约 2–3 分钟，可 SKIP_ORACLE=1 ./scripts/up.sh 跳过）..."
  docker compose up -d oracle || log "Oracle 启动失败，可忽略或查看 docker logs tars-insight-oracle"
fi

echo ""
docker compose ps -a
echo ""
log "连接信息:"
cat "${ROOT}/connections.env"
