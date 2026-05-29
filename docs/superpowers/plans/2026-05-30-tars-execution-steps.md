# TARS v4.3.3 执行步骤编排

> **关联计划**: [2026-05-30-tars-hardening-roadmap.md](2026-05-30-tars-hardening-roadmap.md) — 11 任务的逐步代码 + 验证命令 + commit  
> **目标**: 把 v4.3.2 从"功能完整原型"加固为"可信可交付可扩展"的工程资产  
> **日期**: 2026-05-30  
> **版本**: v4.3.3 开发计划

---

## 一、依赖链总览

```
┌─────────────────────────────────────────────────────────────────┐
│                        BATCH 1 — 基础安全网                       │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │
│  │ Task 1   │  │ Task 2   │  │ Task 3   │  │ Task 4           │ │
│  │ 工具配置  │  │ Gitee CI │  │ pre-commit│  │ DB 表征测试      │ │
│  │ 并行 ✅   │  │ 并行 ✅   │  │ 并行 ✅   │  │ 并行 ✅(安全网)   │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────┬───────────┘ │
│                                                    │ 表征测试必须先于拆分  │
└────────────────────────────────────────────────────┼────────────┘
                                                     │
                        ┌────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                      BATCH 2 — 三大上帝文件拆分                    │
│                                                                  │
│  ┌─────────────────┐     ┌─────────────────┐                    │
│  │ Task 5          │     │ Task 7          │                    │
│  │ models+connection│    │ agent.py 拆分    │                    │
│  │      │           │     │ 独立 ✅          │                    │
│  │      ▼           │     └────────┬────────┘                    │
│  │ Task 6          │              │                              │
│  │ repositories    │              │                              │
│  │ (依赖 Task 5)   │              │                              │
│  └────────┬────────┘              │                              │
│           │                       │                              │
│           │     ┌─────────────────┘                              │
│           │     │                                                │
│           │     │     ┌─────────────────┐                        │
│           │     │     │ Task 8          │                        │
│           │     │     │ main.py 拆分    │                        │
│           │     │     │ 独立 ✅          │                        │
│           │     │     └────────┬────────┘                        │
│           │     │              │                                  │
│           │     │              │                                  │
└───────────┼─────┼──────────────┼──────────────────────────────────┘
            │     │              │
            ▼     ▼              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      BATCH 3 — 产品化 + 差异化                     │
│                                                                  │
│  ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐│
│  │ Task 9          │   │ Task 10         │   │ Task 11         ││
│  │ DB 抽象接口      │   │ Memory MCP      │   │ Evolution Dash  ││
│  │ (依赖 Task 6)   │   │ 独立 ✅          │   │ (依赖 Task 8)   ││
│  └─────────────────┘   └─────────────────┘   └─────────────────┘│
│                                                                  │
│  三任务可并行（各自领域独立）                                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 二、三批次任务明细

### BATCH 1 — 基础安全网（预计 1 天）

> **目标**: 建立 CI/pre-commit/表征测试的安全网，后续所有重构均受此网保护。所有任务零代码逻辑变更。

| # | 任务 | 文件变更 | 类型 | 风险 | 耗时 |
|:---:|------|----------|:---:|:---:|:---:|
| 1 | 补全 lint/test/format 工具配置 | 改 `backend/pyproject.toml` | 配置 | 🟢 低 | 15min |
| 2 | 建立 Gitee Go 流水线 | 建 `.workflow/ci.yml` | 配置 | 🟢 低 | 15min |
| 3 | 配置 pre-commit 本地预检 | 建 `.pre-commit-config.yaml` | 配置 | 🟢 低 | 15min |
| 4 | Database 类表征测试 | 建 `backend/tests/test_database_facade_characterization.py` | 测试 | 🟡 中 | 30min |

**执行顺序**: 四任务完全并行，无依赖。Task 4 产出的是后续所有拆分的安全网。

**出口标准**:
- Task 1: `ruff check .` 可跑，`pytest -q --co` 可收集用例
- Task 2: `.workflow/ci.yml` 本地预演通过（`ruff check` + `pytest -q` + `npm run build`）
- Task 3: `pre-commit run --all-files` 跑过
- Task 4: 4 条表征测试全通过，锁定 Database public API 行为

---

### BATCH 2 — 三大上帝文件拆分（预计 2-3 天）

> **目标**: `database/base.py`(2972行)、`agent.py`(1262行)、`main.py`(1406行) 拆分为可维护模块。**对外签名零变更**，调用方零改动。

#### 子链 A: Database 拆分（Task 5 → Task 6）

| # | 任务 | 文件变更 | 类型 | 风险 | 耗时 | 依赖 |
|:---:|------|----------|:---:|:---:|:---:|:---:|
| 5 | 拆出 models + connection | 建 `models.py` `connection.py`；改 `base.py` | 重构 | 🟡 中 | 1h | Task 4 |
| 6 | 拆出 4 个 repository，base.py 变门面 | 建 `repositories/` 下 5 个文件；改 `base.py` | 重构 | 🔴 高 | 2-3h | Task 5 |

> Task 6 是整个计划中**风险最高**的任务：91 个方法按领域分拆到 4 个 repo，base.py 保留门面委派。每一步必须跑 Task 4 表征测试 + 全量测试。

#### 子链 B: Agent 拆分（Task 7）

| # | 任务 | 文件变更 | 类型 | 风险 | 耗时 | 依赖 |
|:---:|------|----------|:---:|:---:|:---:|:---:|
| 7 | 拆分 agent.py | 建 `prompt_builder.py` `tool_runner.py` `loop.py`；改 `agent.py` | 重构 | 🟡 中 | 1.5h | 无（先写 smoke test） |

#### 子链 C: Main 拆分（Task 8）

| # | 任务 | 文件变更 | 类型 | 风险 | 耗时 | 依赖 |
|:---:|------|----------|:---:|:---:|:---:|:---:|
| 8 | 拆分 main.py | 建 `app_factory.py` `lifespan.py`；改 `main.py` | 重构 | 🟡 中 | 1h | 无（先写 boot test） |

**并行策略**: Task 5→6 串行；Task 7 与 Task 8 可与 5-6 **并行**执行（各自文件域独立）。

**出口标准**:
- Task 5-6: 表征测试 4 passed + 全量测试零新增失败 + `wc -l base.py` ≤ 400 行
- Task 7: smoke test passed + 全量零新增失败 + agent.py ≤ 150 行
- Task 8: boot test passed + 全量零新增失败 + main.py ≤ 5 行

---

### BATCH 3 — 产品化 + 差异化（预计 2 天）

> **目标**: Task 9 为未来 Postgres 留缝；Task 10 让记忆系统对外可集成；Task 11 让自进化指标可视化。三任务领域独立可并行。

| # | 任务 | 文件变更 | 类型 | 风险 | 耗时 | 依赖 |
|:---:|------|----------|:---:|:---:|:---:|:---:|
| 9 | DB 抽象接口 + SQL 方言隔离 | 建 `base_repo.py` `sql_dialect.py`；改各 repo | 架构 | 🟡 中 | 1h | Task 6 |
| 10 | Memory MCP server | 建 `mcp/tars_memory_server.py`；改 `requirements.txt` | 功能 | 🟢 低 | 1h | 无 |
| 11 | Evolution dashboard API + 前端 | 建 `evolution_metrics.py` `EvolutionDashboard.vue`；改 `app_factory.py` | 功能 | 🟡 中 | 1.5h | Task 8 |

**出口标准**:
- Task 9: 方言测试 passed + 表征测试仍全过
- Task 10: MCP 测试 passed + `python mcp/tars_memory_server.py` 不报错
- Task 11: API 测试 passed + `npm run build` 成功

---

## 三、每任务风险评估

| # | 任务 | 风险 | 最大风险点 | 缓解措施 |
|:---:|------|:---:|------|------|
| 1 | 工具配置 | 🟢 低 | 已有 pyproject.toml 配置冲突 | 先 `grep` 检查现有段，有则跳过 |
| 2 | Gitee CI | 🟢 低 | Gitee Go 环境差异 | 本地预演相同命令链 |
| 3 | pre-commit | 🟢 低 | 已安装 hook 冲突 | 先 `pre-commit clean` |
| 4 | DB 表征测试 | 🟡 中 | 方法签名与测试不匹配 | 以真实签名为准修正测试 |
| 5 | models+connection | 🟡 中 | import 路径遗漏 | 每迁出一个类跑一次测试 |
| 6 | repositories 拆分 | 🔴 **高** | 91 方法门面委派遗漏或签错 | 每迁完一个 repo→立刻跑表征测试；Task 4 是安全网 |
| 7 | agent.py 拆分 | 🟡 中 | 循环导入；agent 构造签名变化 | 先写 smoke test 锁定行为 |
| 8 | main.py 拆分 | 🟡 中 | lifespan 钩子顺序错误 | 先写 boot test 验证可启动 |
| 9 | DB 抽象接口 | 🟡 中 | 方言切换 break 现有查询 | 仅抽离硬编码 MATCH，不改查询逻辑 |
| 10 | Memory MCP | 🟢 低 | MemoryManager 构造参数不匹配 | 读 manager.py 前 40 行对齐 |
| 11 | Evolution Dash | 🟡 中 | get_stats() 返回结构不匹配 | API 测试驱动，先写测试再实现 |

---

## 四、执行纪律

### 通用规则

1. **每任务独立 commit**：一次 commit = 一个 Task，不跨任务合并
2. **测试先行**：涉及重构的任务（4,5,6,7,8,9）必须先写/跑测试，再动手改代码
3. **小步提交**：Task 内每个 Step 完成后 `git diff` 确认范围正确
4. **表征测试不可绕过**：Task 6 每迁出一个 repo 必须跑一次 Task 4 的 4 条测试
5. **全量回归常态化**：每个 Task 结束时跑一次 `pytest -q`，确保零新增失败

### 分支策略

```bash
# 从 v4.3.2 切出功能分支
git checkout v4.3.2
git checkout -b hardening/v4.3.3

# 每完成一个 Task:
#   git add <task_files>
#   git commit -m "<task_conventional_commit>"

# 全部完成后合并回主分支
git checkout v4.3.2
git merge --no-ff hardening/v4.3.3
git tag v4.3.3
```

### 回滚策略

| 场景 | 操作 |
|------|------|
| 单个 Task 失败 | `git reset --hard HEAD~1` 回到上一个 commit |
| Batch 2 拆分引入回归 | 表征测试会捕获；若表征测试未覆盖导致漏网 → `git revert` 该 task commit |
| 全批回滚 | `git checkout v4.3.2`，从失败批次前最后一个 commit 重新开始 |
| Task 6 失败（最高风险） | 若门面委派签错导致调用方崩溃，回退到 Task 5 commit 重新拆 |

### 禁止事项

- ❌ 拆分同时改业务逻辑（重构与功能变更分离）
- ❌ 跳过测试直接 commit（违反 TDD 纪律）
- ❌ 合并 commit（保持每 Task 一个 commit，便于 blame）
- ❌ 在 Batch 2 过程中手动修改任何 API 路由或调用方

---

## 五、执行模式

| 模式 | 适用场景 | 说明 |
|------|----------|------|
| **SEQ** | 有严格依赖的任务 | 如 Task 5→6；必须在同一个分支上按序执行 |
| **PAR** | 文件域完全独立的任务 | 如 Batch 1 四任务；Batch 2 的 5-6 与 7 与 8 |
| **TDD** | 所有重构任务 | 先写测试→红→实现→绿→commit |
| **FACADE** | Task 5-6 | 门面模式：对外签名零变更，内部委派 |

### 推荐执行节奏

```
Day 1 上午: Batch 1 (4 任务并行, ~1.5h)
Day 1 下午: Task 5 + Task 6 (database 拆分, ~4h)
Day 2 上午: Task 7 + Task 8 (agent+main 拆分, 并行 ~2.5h)
Day 2 下午: 全量回归 + Task 9
Day 3 上午: Task 10 + Task 11 (并行 ~2.5h)
Day 3 下午: 全计划验收 Checklist
```

### 验收 Checklist（全计划完成后）

- [ ] Gitee Go 流水线在 push 时全部绿灯（lint + test + frontend build）
- [ ] `wc -l base.py agent.py main.py` — 三个文件均显著瘦身（base.py ≤ 400，agent.py ≤ 150，main.py ≤ 5）
- [ ] `cd backend && pytest -q` — 零新增失败（相对计划开始基线）
- [ ] `python mcp/tars_memory_server.py` 不报错，可被外部 MCP 宿主接入
- [ ] `/api/evolution/metrics?tenant_id=default` 返回 stats + recent_feedback
- [ ] `cd frontend && npm run build` 成功（含新 EvolutionDashboard 页面）
- [ ] `git tag v4.3.3` 已打好

---

## 六、与详细实施计划的关系

本文档是**编排视图**，提供依赖链、批次划分、风险矩阵和执行纪律。

**逐步代码 + 验证命令 + commit 信息**请查阅:
→ [2026-05-30-tars-hardening-roadmap.md](2026-05-30-tars-hardening-roadmap.md)

两文档互补：
- **Hardening Roadmap**: "怎么做"（代码细节、验证步骤、commit message）
- **Execution Steps（本文档）**: "什么顺序做"（依赖链、批次、风险、纪律）

---

*关联文档*:
- 详细实施计划: [docs/superpowers/plans/2026-05-30-tars-hardening-roadmap.md](2026-05-30-tars-hardening-roadmap.md)
- 分支: `hardening/v4.3.3` ← `v4.3.2`
- 目标 tag: `v4.3.3`
