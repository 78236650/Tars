# 使用已有 MySQL Docker（不另起 tars-insight-mysql）

你本机已有运行中的 MySQL 时，**不必**再执行 `docker compose up mysql`。

## 1. 导入测试库（一次性）

在**系统终端**执行（按你的账号改端口/密码）：

```bash
cd /Users/daobanxiang/myproject/TARS/deploy/insightforge-db

# 常见：本机映射 3306，用户 root
export MYSQL_HOST=127.0.0.1
export MYSQL_PORT=3306
export MYSQL_USER=root
export MYSQL_PASSWORD=你的密码

./scripts/use-existing-mysql.sh
```

脚本会：

- 创建库 `insight_demo`（可用 `MYSQL_DATABASE` 改名）
- 导入 `init/mysql/01_insight_demo.sql`（订单/用户/商品等）
- 打印 TARS 用的 `connection_url`

## 2. 在 TARS 添加数据源

BI 工作台 → 添加数据源：

| 字段 | 值 |
|------|-----|
| 名称 | 鉴数Demo-已有MySQL |
| 类型 | `mysql` |
| 连接 URL | 上一步脚本输出的 `mysql+pymysql://...` |

或 API：

```http
POST /api/datasources/
Content-Type: application/json
X-Tenant-Id: default

{
  "name": "鉴数Demo-已有MySQL",
  "db_type": "mysql",
  "connection_url": "mysql+pymysql://root:密码@127.0.0.1:3306/insight_demo"
}
```

## 3. 一键鉴数

```http
POST /api/insight/datasources/{id}/profile
Content-Type: application/json

{"force": false}
```

## 4. 验收

```sql
USE insight_demo;
SELECT COALESCE(SUM(amount), 0) AS gmv FROM orders WHERE status = 'paid';
-- 期望: 4197.00
```

Chat 使用角色 **鉴数分析师**，问：「已支付订单 GMV 是多少？」

## 5. 与其他库的关系

| 库 | 是否必须 |
|----|----------|
| **已有 MySQL** | ✅ 你现在用这个即可 |
| PostgreSQL / Oracle / Doris | 测多方言时再 `docker compose --profile full up -d` |

## 6. 查看已有 MySQL 端口

```bash
docker ps --format 'table {{.Names}}\t{{.Ports}}' | grep -i mysql
```

映射里 `0.0.0.0:3306->3306` 则 `MYSQL_PORT=3306`。
