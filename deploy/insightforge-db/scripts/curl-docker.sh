#!/usr/bin/env bash
set -euo pipefail
SOCK="/Users/daobanxiang/.docker/run/docker.sock"
ROOT="/Users/daobanxiang/myproject/TARS/deploy/insightforge-db"
PROJECT="tars-insight-db"

dcurl() {
  local method="$1"; shift
  local path="$1"; shift
  local data="${1:-}"
  if [[ -n "$data" ]]; then
    curl -sS --unix-socket "$SOCK" -X "$method" -H "Content-Type: application/json" "http://localhost${path}" -d "$data"
  else
    curl -sS --unix-socket "$SOCK" -X "$method" "http://localhost${path}"
  fi
}

ensure_volume() {
  local vol="$1"
  dcurl POST "/volumes/create" "{\"Name\":\"${vol}\"}" >/dev/null 2>&1 || true
}

ensure_network() {
  local net="${PROJECT}_default"
  dcurl POST "/networks/create" "{\"Name\":\"${net}\",\"Labels\":{\"com.docker.compose.project\":\"${PROJECT}\"}}" >/dev/null 2>&1 || true
  echo "$net"
}

container_id_by_name() {
  local name="$1"
  dcurl GET "/containers/json?all=1" | tr '{' '\n' | grep -F "\"/${name}\"" | head -1 | sed -n 's/.*"Id":"\([^"]*\)".*/\1/p'
}

start_service_mysql() {
  local cname="tars-insight-mysql"
  local id
  id=$(container_id_by_name "$cname" || true)
  if [[ -n "${id:-}" ]]; then
    dcurl POST "/containers/${id}/start" >/dev/null || true
    echo "mysql: existing ${id}"
    return
  fi
  ensure_volume "${PROJECT}_insight_mysql_data"
  local net; net=$(ensure_network)
  local body
  body=$(cat <<JSON
{
  "Image": "mysql:8.0",
  "Env": [
    "MYSQL_ROOT_PASSWORD=root_insight",
    "MYSQL_DATABASE=insight_demo",
    "MYSQL_USER=insight",
    "MYSQL_PASSWORD=insight_pass"
  ],
  "Cmd": [
    "--character-set-server=utf8mb4",
    "--collation-server=utf8mb4_unicode_ci",
    "--default-authentication-plugin=mysql_native_password"
  ],
  "Labels": {
    "com.docker.compose.project": "${PROJECT}",
    "com.docker.compose.service": "mysql"
  },
  "ExposedPorts": {"3306/tcp": {}},
  "HostConfig": {
    "NetworkMode": "${net}",
    "PortBindings": {"3306/tcp": [{"HostPort": "3307"}]},
    "Binds": [
      "${ROOT}/init/mysql:/docker-entrypoint-initdb.d:ro",
      "${PROJECT}_insight_mysql_data:/var/lib/mysql"
    ],
    "RestartPolicy": {"Name": "unless-stopped"}
  },
  "Healthcheck": {
    "Test": ["CMD", "mysqladmin", "ping", "-h", "127.0.0.1", "-uinsight", "-pinsight_pass"],
    "Interval": 5000000000,
    "Timeout": 5000000000,
    "Retries": 20,
    "StartPeriod": 30000000000
  }
}
JSON
)
  local resp
  resp=$(dcurl POST "/containers/create?name=${cname}" "$body")
  id=$(echo "$resp" | sed -n 's/.*"Id":"\([^"]*\)".*/\1/p')
  if [[ -z "$id" ]]; then echo "mysql create failed: $resp" >&2; return 1; fi
  dcurl POST "/containers/${id}/start" >/dev/null
  echo "mysql: created ${id}"
}

start_service_postgres() {
  local cname="tars-insight-postgres"
  local id
  id=$(container_id_by_name "$cname" || true)
  if [[ -n "${id:-}" ]]; then
    dcurl POST "/containers/${id}/start" >/dev/null || true
    echo "postgres: existing ${id}"
    return
  fi
  ensure_volume "${PROJECT}_insight_pg_data"
  local net; net=$(ensure_network)
  local body
  body=$(cat <<JSON
{
  "Image": "postgres:16-alpine",
  "Env": [
    "POSTGRES_DB=insight_demo",
    "POSTGRES_USER=insight",
    "POSTGRES_PASSWORD=insight_pass"
  ],
  "Labels": {
    "com.docker.compose.project": "${PROJECT}",
    "com.docker.compose.service": "postgres"
  },
  "ExposedPorts": {"5432/tcp": {}},
  "HostConfig": {
    "NetworkMode": "${net}",
    "PortBindings": {"5432/tcp": [{"HostPort": "5433"}]},
    "Binds": [
      "${ROOT}/init/postgres:/docker-entrypoint-initdb.d:ro",
      "${PROJECT}_insight_pg_data:/var/lib/postgresql/data"
    ],
    "RestartPolicy": {"Name": "unless-stopped"}
  },
  "Healthcheck": {
    "Test": ["CMD-SHELL", "pg_isready -U insight -d insight_demo"],
    "Interval": 5000000000,
    "Timeout": 5000000000,
    "Retries": 20,
    "StartPeriod": 15000000000
  }
}
JSON
)
  local resp
  resp=$(dcurl POST "/containers/create?name=${cname}" "$body")
  id=$(echo "$resp" | sed -n 's/.*"Id":"\([^"]*\)".*/\1/p')
  if [[ -z "$id" ]]; then echo "postgres create failed: $resp" >&2; return 1; fi
  dcurl POST "/containers/${id}/start" >/dev/null
  echo "postgres: created ${id}"
}

start_service_doris() {
  local cname="tars-insight-doris"
  local id
  id=$(container_id_by_name "$cname" || true)
  if [[ -n "${id:-}" ]]; then
    dcurl POST "/containers/${id}/start" >/dev/null || true
    echo "doris: existing ${id}"
    return
  fi
  ensure_volume "${PROJECT}_insight_doris_meta"
  ensure_volume "${PROJECT}_insight_doris_storage"
  local net; net=$(ensure_network)
  local body
  body=$(cat <<JSON
{
  "Image": "docker.io/dyrnq/doris:3.0.6.2",
  "Hostname": "tars-insight-doris",
  "Env": ["TZ=Asia/Shanghai", "RUN_MODE=standalone"],
  "Labels": {
    "com.docker.compose.project": "${PROJECT}",
    "com.docker.compose.service": "doris"
  },
  "ExposedPorts": {"9030/tcp": {}, "8030/tcp": {}},
  "HostConfig": {
    "NetworkMode": "${net}",
    "Privileged": true,
    "PortBindings": {
      "9030/tcp": [{"HostPort": "9030"}],
      "8030/tcp": [{"HostPort": "8030"}]
    },
    "Binds": [
      "${PROJECT}_insight_doris_meta:/opt/apache-doris/fe/doris-meta",
      "${PROJECT}_insight_doris_storage:/opt/apache-doris/be/storage"
    ],
    "RestartPolicy": {"Name": "unless-stopped"}
  },
  "Healthcheck": {
    "Test": ["CMD-SHELL", "bash -c 'echo > /dev/tcp/127.0.0.1/9030'"],
    "Interval": 10000000000,
    "Timeout": 5000000000,
    "Retries": 30,
    "StartPeriod": 90000000000
  }
}
JSON
)
  local resp
  resp=$(dcurl POST "/containers/create?name=${cname}" "$body")
  id=$(echo "$resp" | sed -n 's/.*"Id":"\([^"]*\)".*/\1/p')
  if [[ -z "$id" ]]; then echo "doris create failed: $resp" >&2; return 1; fi
  dcurl POST "/containers/${id}/start" >/dev/null
  echo "doris: created ${id}"
}

compose_ps() {
  dcurl GET "/containers/json?all=1&filters=%7B%22label%22%3A%5B%22com.docker.compose.project%3Dtars-insight-db%22%5D%7D%7D"
}

pull_image() {
  local img="$1"
  echo "[curl-docker] pull ${img} ..."
  dcurl POST "/images/create?fromImage=${img}" "" >/dev/null 2>&1 || true
}

case "${1:-}" in
  up-mysql-postgres-doris)
    if [[ ! -S "$SOCK" ]]; then
      echo "[curl-docker] Docker sock 不存在: $SOCK — 请先打开 Docker Desktop" >&2
      exit 1
    fi
    pull_image "mysql&tag=8.0"
    pull_image "postgres&tag=16-alpine"
    pull_image "dyrnq/doris&tag=3.0.6.2"
    start_service_mysql || exit 1
    start_service_postgres || echo "[curl-docker] postgres 失败，继续..."
    start_service_doris || echo "[curl-docker] doris 失败，可稍后重试"
    echo "[curl-docker] done. 运行: bash scripts/seed-doris.sh"
    ;;
  ps) compose_ps ;;
  *) echo "usage: $0 up-mysql-postgres-doris|ps" >&2; exit 1 ;;
esac
