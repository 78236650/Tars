# BI Analytics Skill 设计

## 核心决策

1. **多数据库支持**：通过 SQLAlchemy 统一抽象（MySQL/PostgreSQL/Oracle/SQL Server/ClickHouse）
2. **输出形式**：文本总结 + ECharts 图表渲染
3. **Schema 理解**：自动推断 + 用户修正，持久化
4. **安全控制**：只读，仅允许 SELECT
5. **架构模式**：BI Skill 包 + 内部 SQL Agent 自我修正

## 整体结构

```
skills/
└── bi_analytics/
    ├── SKILL.md              # Skill 声明
    ├── main.py               # 入口：注册工具
    ├── tools/
    │   ├── db_connect.py     # 数据源连接管理
    │   ├── schema_explore.py # Schema 抓取 + 理解
    │   └── sql_query.py      # SQL 生成 + 执行（含自我修正）
    └── pipelines/
        └── report.yaml       # 报表生成 pipeline
```

## 数据源模型

```python
DataSource:
  id: str
  tenant_id: str
  name: str                # 显示名，如 "生产库-订单"
  db_type: str             # mysql / postgresql / oracle / sqlserver / clickhouse
  connection_url: str      # SQLAlchemy URL 格式
  readonly: true           # 强制只读
  schema_snapshot: dict    # 缓存的 schema 信息
  schema_annotations: dict # 用户标注的业务含义
  created_at / updated_at
```

连接 URL 格式示例：
- MySQL: `mysql+pymysql://user:pass@host:3306/db`
- PostgreSQL: `postgresql+psycopg2://user:pass@host:5432/db`
- Oracle: `oracle+cx_oracle://user:pass@host:1521/sid`
- SQL Server: `mssql+pymssql://user:pass@host:1433/db`

## Schema 理解流程

```
连接数据源
  → SQLAlchemy inspect() 抓取：表名、字段、类型、注释、外键、索引
  → LLM 推断业务含义（基于命名 + 注释 + 外键关系）
  → 生成 schema_snapshot + 初始 annotations
  → 用户可在前端修正/补充
  → 持久化到 DataSource.schema_annotations
```

标注存储格式：

```json
{
  "orders": {
    "description": "订单主表",
    "columns": {
      "gmv": "成交总额（元）",
      "product_line": "产品线编码，关联 product_lines.code",
      "created_at": "下单时间"
    },
    "relationships": ["orders.user_id → users.id"]
  }
}
```

## SQL Agent（自我修正）

```
用户问题 + schema 上下文
  → LLM 生成 SQL
  → 安全校验（白名单）
  → 执行 SQL
  → 成功？→ 返回结果
  → 失败？→ 错误信息反馈 LLM → 重新生成（最多 3 轮）
```

### 安全层

- SQL 解析白名单：只允许 `SELECT`、`WITH`（CTE）、`EXPLAIN`
- 禁止：`INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE/GRANT`
- 结果集限制：默认 `LIMIT 1000`
- 查询超时：30 秒
- 连接强制 `readonly` 模式

## 图表生成

LLM 根据查询结果推荐图表类型并生成 ECharts option：

```json
{
  "chart_type": "line",
  "title": "各产品线 GMV 月度趋势",
  "echarts_option": { "..." },
  "data_summary": "3 月 A 产品线 GMV 环比增长 23%...",
  "raw_data": [{"..."}]
}
```

支持图表类型：line / bar / pie / scatter / table

## 前端变更

| 组件 | 说明 |
|------|------|
| `ChartRenderer.vue` | 接收 ECharts option，渲染图表 |
| `DataSourceSettings.vue` | 数据源 CRUD + 连接测试 |
| `SchemaAnnotator.vue` | 表/字段业务含义编辑器 |
| `ChatMessage` 扩展 | 识别 BI 响应，渲染图表 + 表格 |

## 后端 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/datasources` | GET | 获取当前租户数据源列表 |
| `/api/datasources` | POST | 创建数据源 + 自动抓取 schema |
| `/api/datasources/{id}` | PUT | 更新数据源配置 |
| `/api/datasources/{id}` | DELETE | 删除数据源 |
| `/api/datasources/{id}/test` | POST | 测试连接 |
| `/api/datasources/{id}/refresh-schema` | POST | 重新抓取 schema |
| `/api/datasources/{id}/annotations` | PUT | 更新 schema 标注 |

## 工作流示例

```
用户: "帮我看下上个月各产品线的 GMV 趋势"

Agent:
  1. BI Skill 激活
  2. 从 schema_annotations 找到 orders 表（含 gmv、product_line、created_at）
  3. SQL Agent 生成:
     SELECT product_line, DATE(created_at) as dt, SUM(gmv) as total_gmv
     FROM orders
     WHERE created_at >= '2026-04-01' AND created_at < '2026-05-01'
     GROUP BY product_line, dt ORDER BY dt
  4. 执行成功，返回 45 行数据
  5. LLM 推荐折线图 + 生成 ECharts option + 文字总结
  6. 前端渲染图表 + 显示总结文字
```

## 依赖

```
sqlalchemy>=2.0
pymysql
psycopg2-binary
cx_oracle        # Oracle 可选
pymssql          # SQL Server 可选
sqlparse         # SQL 解析/白名单校验
```

## 实施优先级

```
Step 1: DataSource 模型 + CRUD API + 连接测试
Step 2: Schema 抓取 + LLM 推断 + 标注界面
Step 3: SQL Agent（生成 + 执行 + 自我修正 + 安全校验）
Step 4: 图表生成（LLM 推荐 + ECharts option）
Step 5: 前端 ChartRenderer + ChatMessage 集成
```
