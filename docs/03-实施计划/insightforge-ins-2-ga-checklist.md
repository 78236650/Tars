# InsightForge INS-2.0.0 GA 验收清单

对照 [INS-2.0 产品设计](../superpowers/specs/2026-05-20-insightforge-ins-2-redesign.md) §十二。

| 项 | 状态 | 说明 |
|----|------|------|
| E2：选源 → 鉴数 → 问数 → 采用，可不打开 W1 | ✅ | Chat WorkflowStrip + `/问数` + adopt |
| V2 + §3.3.1 首问接续（TTL 从 `ready` 起算，H5） | ✅ | `job_runner._auto_ask_pending` |
| 双层状态：同步 `/ask` 不写 `asking`（H2） | ✅ | 仅 `/ask/stream` 写 session asking |
| **eval_set.yaml ≥80%**（H8） | ✅ | 10/10 = 100%，`pytest -m insight_eval` |
| 三档标签正确 | ✅ | official / suggested / adhoc |
| `insight_analyst` 零 chart/python | ✅ | `role_template` denied_tools |
| W1 无 LLM 主面板 | ✅ | 迁至 `/admin/insight/llm` |
| SSE 重连 + `/workflow` | ✅ | M1 workflow_events |
| workers=1 或 sticky（H1） | ✅ | [部署说明](../04-运维文档/insightforge-deploy.md) |
| `require_review=false` Chat 一键 official | ✅ | `adoption_service` + MetricAnswerCard |
| few-shot token budget ≤2000（H4） | ✅ | `question_log_store.select_for_prompt` |
| 👎 降级可配置（H3） | ✅ | `insight.yaml` feedback.* |

**发布：** 打 tag `insight-v2.0.0`（由发布负责人在合并后执行）。
