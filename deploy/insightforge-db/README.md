# InsightForge 本地测试数据库 (Docker)

为 **鉴数 INS-1.0.0** 提供多库测试数据（订单 / 用户 / 商品 / 产品线）。

## 已有 MySQL Docker？直接用

**不必再起一个 MySQL 容器。** 见 **[EXISTING-MYSQL.md](EXISTING-MYSQL.md)**：

```bash
cd deploy/insightforge-db
MYSQL_PORT=3306 MYSQL_USER=root MYSQL_PASSWORD=你的密码 ./scripts/use-existing-mysql.sh
```

然后在 TARS BI 里添加输出的 `connection_url`，执行鉴数 Profile 即可。

## 业务数据说明

| 表 | 角色 |
|----|------|
| `product_lines` | 产品线维度 |
| `users` | 用户维度 |
| `products` | 商品维度 |
| `orders` | 订单事实（`amount` = GMV，`status`: paid/pending/refunded） |
| `order_items` | 订单明细 |

**验收指标**：已支付 GMV

```sql
SELECT COALESCE(SUM(amount), 0) AS gmv FROM orders WHERE status = 'paid';
-- 期望结果: 4197.00
```

## 快速开始

**重要**：Cursor 内置终端里 `docker` 常会报 `permission denied`，请用下面任一方式：

### 方式 A（推荐）：双击启动

在 Finder 中双击：

`deploy/insightforge-db/Run-Insight-DB.command`

（首次右键 → 打开，允许运行）

### 方式 B：系统终端

```bash
cd /Users/daobanxiang/myproject/TARS/deploy/insightforge-db
chmod +x scripts/*.sh
./scripts/up.sh
./scripts/verify.sh
```

启动前请确认 **Docker Desktop 状态为 Running**。

仅启动部分库：

```bash
docker compose up -d mysql postgres
```

停止并删除容器（保留 volume）：

```bash
./scripts/down.sh
```

停止并清空数据：

```bash
docker compose down -v
```

## 端口

| 服务 | 宿主机端口 | 说明 |
|------|------------|------|
| MySQL | 3307 | 避免与本地 3306 冲突 |
| PostgreSQL | 5433 | 避免与本地 5432 冲突 |
| Oracle | 1521 | 首次启动约 2–3 分钟 |
| Doris FE | 9030 / 8030 | MySQL 协议查询 |

## TARS 接入

连接串见 [`connections.env`](connections.env)。在 BI 工作台添加数据源后执行鉴数：

```http
POST /api/insight/datasources/{id}/profile
```

### 角色建议

- **鉴数**：`insight_analyst` — 问「已支付 GMV 是多少？」
- **原型图**：切 `analyst` + `python_exec`

## Doris 注意

- 镜像 `dyrnq/doris:3.0.6.2` 单机模式，需 `privileged: true`
- macOS / Linux 若启动失败，可尝试：
  ```bash
  sysctl -w vm.max_map_count=2000000
  ```
- 数据由 `scripts/seed-doris.sh` 在 FE 就绪后导入

## Oracle 注意

- 镜像 `gvenzl/oracle-free:23-slim-faststart`
- 应用用户：`insight` / `insight_pass`
- Python 驱动：`pip install oracledb`

## 运行 Docker 集成测试（可选）

```bash
cd backend
INSIGHT_DOCKER_TEST=1 pytest tests/test_insight_docker_smoke.py -v
```

未启动 Docker 时自动 skip。
