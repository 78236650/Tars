#!/usr/bin/env bash
# 在「已有」的 MySQL Docker / 实例上创建 insight_demo 测试库
#
# 用法示例:
#   MYSQL_HOST=127.0.0.1 MYSQL_PORT=3306 MYSQL_USER=root MYSQL_PASSWORD=你的密码 ./scripts/use-existing-mysql.sh
#
# 或用 mysql 客户端直接执行:
#   mysql -h127.0.0.1 -P3306 -uroot -p < init/mysql/01_insight_demo.sql
#   (需先: CREATE DATABASE IF NOT EXISTS insight_demo; USE insight_demo;)

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SQL="${ROOT}/init/mysql/01_insight_demo.sql"

HOST="${MYSQL_HOST:-127.0.0.1}"
PORT="${MYSQL_PORT:-3306}"
USER="${MYSQL_USER:-root}"
PASS="${MYSQL_PASSWORD:-}"
DB="${MYSQL_DATABASE:-insight_demo}"

if [[ -z "$PASS" ]]; then
  read -rsp "MySQL 密码 (${USER}@${HOST}:${PORT}): " PASS
  echo ""
fi

export MYSQL_PWD="$PASS"

echo "[insight-db] 创建库 ${DB} ..."
mysql -h"$HOST" -P"$PORT" -u"$USER" -e "CREATE DATABASE IF NOT EXISTS \`${DB}\` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

echo "[insight-db] 导入 Demo 表与数据 ..."
mysql -h"$HOST" -P"$PORT" -u"$USER" "$DB" < "$SQL"

echo "[insight-db] 验收 GMV (已支付) ..."
GMV=$(mysql -h"$HOST" -P"$PORT" -u"$USER" "$DB" -N -e "SELECT COALESCE(SUM(amount),0) FROM orders WHERE status='paid';")
echo "GMV = ${GMV}  (期望 4197.00)"

ENC_PASS=$(python3 -c "import urllib.parse; print(urllib.parse.quote('''${PASS}''', safe=''))" 2>/dev/null || echo "$PASS")

echo ""
echo "=========================================="
echo " TARS BI 数据源连接串（复制到工作台）:"
echo "=========================================="
echo "名称: 鉴数Demo-已有MySQL"
echo "db_type: mysql"
echo "connection_url:"
echo "mysql+pymysql://${USER}:${ENC_PASS}@${HOST}:${PORT}/${DB}"
echo ""
echo "鉴数冷启动:"
echo "  POST /api/insight/datasources/{数据源id}/profile"
echo "=========================================="

unset MYSQL_PWD
