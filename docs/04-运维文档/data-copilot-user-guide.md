# TARS v4.2.0 数据 Copilot 用户指南

本文档说明 Phase 1「内网数据/分析 Copilot」的模块入口、角色权限与典型工作流。

## 1. 模块入口

| 模块 | 路径 | 适用人群 | 能力 |
|------|------|----------|------|
| **鉴数 InsightForge** | `/insight` | 业务分析师（80%） | 问指标、查口径、引用知识库 |
| **BI 分析** | `/bi` | 数据工程师（20%） | SQL 查询、图表生成 |
| **知识库** | `/knowledge` | 全员 | 上传文档、关联指标 |
| **聊天** | `/` | 全员 | 通用对话（不含 BI SQL） |

左侧导航在 **鉴数** 与 **BI** 下显示副标题，便于区分「问指标/口径」与「SQL/图表」。

## 2. 角色与权限

| 角色 | insight | bi | knowledge | 说明 |
|------|---------|-----|-----------|------|
| `business_analyst` | ✅ | ❌ | ✅ | 推荐业务用户默认角色 |
| `insight_analyst` | ✅ | ❌ | ✅ | 鉴数专项，不含 BI |
| `standard` | ✅ | ❌ | ✅ | 通用用户 |
| `data_analyst` | ✅ | ✅ | ✅ | 工程师，BI + 鉴数 |

登录后系统会加载 `initSettings()`，按全局模块开关与角色 `allowed_modules` 过滤导航项。

## 3. 业务分析师路径（问数）

1. 进入 **鉴数** → 选择数据源 → 完成 InsightForge 建档（若尚未 ready）。
2. 在问数面板输入自然语言问题，例如「昨日 GMV 是多少？」。
3. 查看 **MetricAnswerCard**：
   - 数值与 **口径 tier**（official / suggested / adhoc）
   - **引用 chips**：`[ref:doc_id|标题]` 来自鉴数说明书、会议摘要或关联文档
4. 若口径为 suggested/adhoc，可 **👍/👎** 反馈或 **采用为官方指标**；采用后自动写入知识库 metric card。

## 4. 工程师路径（SQL）

1. 使用 `data_analyst` 或含 `bi` 模块的角色。
2. 进入 **BI 分析** → 选择数据源 → 编写/生成 SQL → 出图。
3. 复杂口径问题仍建议先在 **鉴数** 确认 metric_key 与 definition，再回到 BI 写 SQL。

## 5. 知识库 ↔ 指标联动

- 上传文档时可填写 `metric_ids`（逗号分隔 UUID），问数时会优先检索关联文档。
- 指标 **采用（adopt）** 后，系统自动在 `insight_{datasource_id}` 集合发布 metric card。

## 6. 部署注意（SSE）

InsightForge 建档进度使用 SSE。生产环境须 **uvicorn workers=1** 或配置 **Ingress sticky session**；多 worker 无 sticky 时启动日志会 ERROR，详见 [insightforge-deploy.md](./insightforge-deploy.md)。

## 7. 验收

运行 `scripts/acceptance/phase1-data-copilot.sh`（需本地后端已启动）进行 Phase 1 手动验收。
