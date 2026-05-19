---
name: bi_analytics
description: BI 数据分析技能。支持连接多种数据库（MySQL/PostgreSQL/Oracle/SQL Server/ClickHouse/SQLite），自动生成 SQL 查询，生成图表和数据分析报告。当用户需要进行数据查询、统计分析、趋势查看、报表生成时使用此技能。
permissions: [database_read]
depends_on: []
outputs:
  chart:
    type: object
    description: ECharts 图表配置
  sql:
    type: string
    description: 执行的 SQL 语句
  data:
    type: array
    description: 查询结果数据
---

# BI Analytics

BI 数据分析技能，帮助用户连接数据库、查询数据、生成图表。

## 使用场景

- "帮我查一下上个月的订单数据"
- "各产品线的 GMV 趋势如何"
- "生成用户增长报表"
- "分析销售数据并画个图"

## 可用工具

1. **bi_list_datasources** - 列出已配置的数据源
2. **bi_query** - 执行 SQL 查询（只读）
3. **bi_generate_chart** - 根据 SQL 结果生成图表

## 工作流程

1. 先调用 `bi_list_datasources` 查看可用数据源
2. 根据用户问题和 schema 信息生成 SQL
3. 调用 `bi_query` 执行查询
4. 调用 `bi_generate_chart` 生成可视化图表
5. 向用户返回文字总结 + 图表
