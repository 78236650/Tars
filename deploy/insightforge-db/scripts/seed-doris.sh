#!/usr/bin/env bash
# 等待 Doris FE 并导入 demo 数据
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SQL_FILE="${ROOT}/init/doris/01_insight_demo.sql"
CONTAINER="${DORIS_CONTAINER:-tars-insight-doris}"
MAX_WAIT="${MAX_WAIT:-120}"

echo "[insight-db] 等待 Doris MySQL 协议端口 9030 (容器 ${CONTAINER})..."
for i in $(seq 1 "$MAX_WAIT"); do
  if docker exec "${CONTAINER}" bash -c 'echo > /dev/tcp/127.0.0.1/9030' 2>/dev/null; then
    echo "[insight-db] Doris 9030 已就绪 (${i}s)"
    break
  fi
  if [[ "$i" -eq "$MAX_WAIT" ]]; then
    echo "[insight-db] Doris 启动超时" >&2
    exit 1
  fi
  sleep 1
done

echo "[insight-db] 执行 Doris 初始化 SQL..."
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1 && docker exec -i "${CONTAINER}" mysql -h127.0.0.1 -P9030 -uroot < "${SQL_FILE}" 2>/dev/null; then
  echo "[insight-db] Doris 数据导入完成"
else
  echo "[insight-db] 尝试使用容器内 mysql 客户端失败，改用宿主机 mysql 客户端..." >&2
  if command -v mysql >/dev/null 2>&1; then
    mysql -h127.0.0.1 -P9030 -uroot < "${SQL_FILE}"
    echo "[insight-db] Doris 数据导入完成 (host mysql)"
  else
    echo "[insight-db] 请安装 mysql 客户端或检查 Doris 容器内 mysql 命令" >&2
    exit 1
  fi
fi
