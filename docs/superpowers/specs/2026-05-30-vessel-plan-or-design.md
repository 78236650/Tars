---
doc_type: spec
status: approved
platform_version: v4.5.0
---

# 船舶进出港计划 · Agent 与运筹优化协同设计

> 日期：2026-05-30  
> 版本：**v4.5.0**  
> 入口：作业调度 `/orchestration` → Tab **进出港计划**

## 1. 目标

在 v4.4.0 作业调度 MVP 之上，新增 **船舶进出港计划** 能力：

- **48 小时滚动** 到港船计划总览
- **单船下钻** 进港→靠泊→作业→离港时间线
- **Agent ↔ OR 闭环**：Agent 预处理约束 → 运筹求解 → Agent 解释/告警/备选
- **微调 + 重算 + 确认下发** 至现有协同调度（berth/yard/vessel）

## 2. 需求决策（已确认）

| 维度 | 选择 |
|------|------|
| 数据 | 内置拟真数据集（元洪 Demo 码头） |
| 视图 | 48h 总览 + 单船下钻 |
| 协同 | Agent 定约束 → OR 求解 → Agent 后处理 |
| 优化目标 | 主：最小化总等待；次：靠近目标堆场 |
| 交互 | 微调泊位/时间 → 重算 → 多选确认下发 |

## 3. 架构

```
/orchestration
├── Tab1 协同作业（现有）
└── Tab2 进出港计划
    ├── BerthGanttChart（泊位×时间）
    ├── BerthLayoutMap（平面泊位图）
    ├── VesselPlanList + Agent 摘要条
    └── VesselTimelineDrawer（单船）

API /api/vessel-plans/*
  → VesselPlanService
      → ShipPlanAgent（前/后处理）
      → BerthScheduler（OR）
      → adopt → POST /api/orchestration/dispatch
```

## 4. 数据模型

| 表 | 用途 |
|----|------|
| `vp_berths` | 泊位参数 + 平面图坐标 + yard_zone |
| `vp_vessels` | 船舶 LOA、吃水、优先级 |
| `vp_voyages` | ETA/ETD、箱量、目标堆场、status |
| `vp_assignments` | 求解结果：berth_id, etb, etd, wait_min, locked |
| `vp_plan_runs` | 优化批次、constraints_json、objective |

租户字段 `tenant_id`，与现有多租户一致。Demo seed 固定 6 泊位、12 航次（48h 内）。

## 5. Agent ↔ OR

**ShipPlanAgent（规则为主，LLM 可选后处理）：**

- 前处理：吃水/船长过滤；VIP 优先级；输出 `constraints_json`
- 后处理：逐船说明；汇总等待；冲突卡片；备选泊位

**BerthScheduler（纯算法）：**

- 按 ETA 排序贪心占位 + 局部交换改进
- 硬约束：泊位不重叠、吃水、船长
- 目标：`Σ wait + λ × yard_distance`

## 6. API

| 方法 | 路径 |
|------|------|
| GET | `/api/vessel-plans/demo/status` |
| POST | `/api/vessel-plans/demo/reset` |
| GET | `/api/vessel-plans/berths` |
| GET | `/api/vessel-plans/horizon?hours=48` |
| POST | `/api/vessel-plans/optimize` |
| PATCH | `/api/vessel-plans/assignments/{voyage_id}` |
| POST | `/api/vessel-plans/recompute` |
| GET | `/api/vessel-plans/voyages/{id}` |
| POST | `/api/vessel-plans/adopt` |

模块开关：随 `orchestration.enabled` 加载（不新增 modules.yaml 项）。

## 7. 前端

- `OrchestrationView` 增加 Tab 切换
- 组件：`BerthGanttChart`、`BerthLayoutMap`、`VesselTimelineDrawer`、`VesselPlanAdjustForm`
- 甘特与平面图联动；下发后跳转 orchestration 详情

## 8. 不在范围

- 真实 TOS / Excel 导入
- 甘特拖拽改时间
- OR-Tools / 大规模 MILP
- 精确潮汐模型

## 9. 验收

- 后端：`pytest tests/test_berth_scheduler.py tests/test_vessel_plan_api.py tests/test_vessel_plan_e2e.py`
- 浏览器：优化 → 改泊位 → 重算 → 下发 → 协同作业可见
- 拟真数据一键 reset 可重复演示
