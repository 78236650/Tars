# InsightForge 鉴数 — 数据库连接说明 (INS-1.0.0)

## 本地 Docker 测试栈

一键启动 MySQL / PostgreSQL / Oracle / Doris 及统一 Demo 数据：

```bash
cd deploy/insightforge-db
./scripts/up.sh
```

详见 [deploy/insightforge-db/README.md](../../deploy/insightforge-db/README.md) 与 `connections.env`。

## 一等公民（完整 Profile）

| db_type | 连接 URL 示例 | 说明 |
|---------|---------------|------|
| `mysql` | `mysql+pymysql://user:pass@host:3306/db` | 标准 MySQL |
| `postgresql` | `postgresql+psycopg2://user:pass@host:5432/db` | PostgreSQL |
| `oracle` | `oracle+oracledb://user:pass@host:1521/?service_name=ORCL` | 或 `oracle+cx_oracle://` |
| `doris` | `mysql+pymysql://user:pass@fe_host:9030/db` | **Doris FE MySQL 协议**，`db_type` 填 `doris` |

### Apache Doris 注意

- 查询端口一般为 **9030**（FE MySQL 协议）
- `db_type` 必须使用 **`doris`**，便于 InsightForge 打标与审计；URL 仍用 `mysql+pymysql`
- 统计与采样复用 MySQL 方言实现；超大表请使用只读账号并调低 `insight.yaml` 中 `profile.max_tables`

## JDBC（降级 Profile）

| db_type | 说明 |
|---------|------|
| `jdbc` | 由运维提供已验证的 SQLAlchemy 兼容 `connection_url`；Profile 使用 `generic` 模式 |

## 只读账号建议

- 仅 `SELECT` / `SHOW` / `DESCRIBE`（及 Doris/MySQL 的 `information_schema` 读权限）
- 禁止 DDL/DML
