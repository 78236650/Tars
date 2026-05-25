# InsightForge 鉴数建档性能优化 INS-2.1

> **状态：** 设计完成，待开发  
> **日期：** 2026-05-24

## 文档索引

| 类型 | 路径 |
|------|------|
| **设计** | [docs/superpowers/specs/2026-05-24-insightforge-profile-perf-design.md](../superpowers/specs/2026-05-24-insightforge-profile-perf-design.md) |
| **实施计划** | [docs/superpowers/plans/2026-05-24-insightforge-profile-perf-plan.md](../superpowers/plans/2026-05-24-insightforge-profile-perf-plan.md) |
| **测试用例集** | [backend/tests/insight/profile_perf_suite.yaml](../../backend/tests/insight/profile_perf_suite.yaml) |

## 范围摘要

针对 Profile P2 统计阶段的四项优化：

1. **表级并行** — 落实 `parallel_tables`
2. **SQL 超时** — 落实 `stats_timeout_sec`
3. **增量建档** — 落实 `enable_incremental`
4. **批量列 SQL** — T1 方言降低查询次数

目标版本：**INS-2.1.0**

## 测试运行

```bash
# 声明式用例（未实现模块自动 skip）
cd backend && pytest tests/insight/test_insight_profile_perf_suite.py -v -m "not insight_perf"

# 性能基准（实现 M4 后）
INSIGHT_PERF_BENCH=1 pytest tests/insight/test_insight_profile_perf_suite.py -v -m insight_perf
```

## 里程碑

| 里程碑 | 内容 |
|--------|------|
| M1 | 并行 + 超时 |
| M2 | 增量建档 |
| M3 | 批量列 SQL |
| M4 | perf 可观测 + 验收脚本 |
