---
doc_type: plan
status: shipped
platform_version: 4.2.0
catalog: docs/superpowers/README.md
---
# TARS v4.2.0 Phase 2: Evolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver full self-evolution on v4.2.0 — unified feedback (A/B/C/D), workspace/skills writeback via ApplyEngine, eval gate with ≥10% improvement and rollback.

**Architecture:** FeedbackCollector → EvolutionOrchestrator → ApplyEngine; EvalRunner gates apply batches. Tenant-scoped only.

**Tech Stack:** Python 3.11 / FastAPI / SQLite / pytest

**Spec:** [2026-05-24-evolution-phase2-design.md](../specs/2026-05-24-evolution-phase2-design.md)

**Depends on:** Phase 1 KnowledgeBridge (for Insight feedback hook C) — can stub C until Phase 1 W6 done.

---

## File Map

| File | Action |
|------|--------|
| `backend/tars/evolution/models.py` | Create |
| `backend/tars/evolution/feedback_collector.py` | Create |
| `backend/tars/evolution/orchestrator.py` | Create |
| `backend/tars/evolution/apply_engine.py` | Create |
| `backend/tars/evolution/eval_runner.py` | Create |
| `backend/tars/evolution/skill_optimizer.py` | Create |
| `backend/tars/evolution/manager.py` | Refactor → delegate to orchestrator |
| `backend/tars/skills/curator.py` | Modify — `record_call(skill_id, success=bool)` |
| `backend/tars/tools/dispatcher.py` | Modify — implicit feedback on tool result |
| `backend/tars/agent/agent.py` | Modify — `ingest_turn` after assistant reply |
| `backend/tars/insight/adoption_service.py` | Modify — insight 👎 → collector |
| `backend/tars/main.py` | Modify — wire ApplyEngine with WorkspaceManager |
| `backend/config/evolution.yaml` | Create |
| `backend/tests/evolution/eval_set.yaml` | Create (≥20 scenarios) |
| `backend/tests/test_evolution_*.py` | Create (6 files) |
| `EVOLUTION_GUIDE.md` | Update |

---

### Task 1: Evolution DB schema + models

**Files:**
- Create: `backend/tars/evolution/models.py`
- Modify: `backend/tars/database/base.py` (migrations)
- Test: `backend/tests/test_evolution_feedback_collector.py`

- [ ] **Step 1: Write failing test for event insert**

```python
def test_feedback_collector_persists_event(db, collector):
    collector.record(EvolutionEvent(
        tenant_id="t1", user_id="u1", source="implicit",
        signal="tool_fail", payload={"tool": "shell"}, weight=1.0,
    ))
    rows = db.list_evolution_events(tenant_id="t1", limit=1)
    assert rows[0].signal == "tool_fail"
```

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest backend/tests/test_evolution_feedback_collector.py -v`

- [ ] **Step 3: Add tables `evolution_events`, `evolution_apply_log`**

- [ ] **Step 4: Implement `FeedbackCollector.record()`**

- [ ] **Step 5: Run — expect PASS**

- [ ] **Step 6: Commit**

---

### Task 2: ApplyEngine — personality writeback

**Files:**
- Create: `backend/tars/evolution/apply_engine.py`
- Test: `backend/tests/test_evolution_apply_engine.py`

- [ ] **Step 1: Test SOUL.md parameters update + audit log**

- [ ] **Step 2: Implement `apply_personality(tenant_id, params)` using WorkspaceManager**

- [ ] **Step 3: Implement `rollback(apply_id)` restoring before_hash snapshot**

- [ ] **Step 4: Replace `EvolutionManager._apply_personality_update` pass with ApplyEngine call**

- [ ] **Step 5: Commit**

---

### Task 3: Agent ingest_turn + auto trigger

**Files:**
- Modify: `backend/tars/agent/agent.py`
- Modify: `backend/tars/evolution/orchestrator.py`
- Modify: `backend/tars/evolution/manager.py`
- Test: `backend/tests/test_evolution_agent_integration.py`

- [ ] **Step 1: Test conversation_count increments and triggers optimize at interval=50 (mock)**

- [ ] **Step 2: Add `EvolutionManager.ingest_turn(...)` at end of agent turn**

- [ ] **Step 3: Wire `_get_current_personality` to read tenant SOUL.md via WorkspaceManager**

- [ ] **Step 4: Commit**

---

### Task 4: Explicit + Insight feedback hooks

**Files:**
- Modify: `backend/tars/main.py` (WS message_feedback if missing)
- Modify: `backend/tars/insight/adoption_service.py`
- Test: extend `test_evolution_feedback_collector.py`

- [ ] **Step 1: Test explicit thumbs_down creates event weight=2.0**

- [ ] **Step 2: Hook Insight `process_feedback` negative → collector**

- [ ] **Step 3: Commit**

---

### Task 5: SkillOptimizer + Curator success

**Files:**
- Create: `backend/tars/evolution/skill_optimizer.py`
- Modify: `backend/tars/skills/curator.py`
- Test: `backend/tests/test_evolution_skill_optimizer.py`

- [ ] **Step 1: Extend skill_usage schema: `success_count`, `fail_count`**

- [ ] **Step 2: `record_call(skill_id, success=True|False)` in dispatcher/skill executor**

- [ ] **Step 3: SkillOptimizer suggests description patch when success_rate < 0.4 and calls >= 10**

- [ ] **Step 4: ApplyEngine.apply_skill_description — patch SKILL.md only**

- [ ] **Step 5: Commit**

---

### Task 6: Prompt + SubAgent writeback

**Files:**
- Modify: `backend/tars/evolution/apply_engine.py`
- Modify: `backend/tars/agent/subagent_manager.py`
- Test: `backend/tests/test_evolution_orchestrator.py`

- [ ] **Step 1: `apply_prompt(tenant_id, prompt_type, content)` → `workspace/prompts/{type}.md`**

- [ ] **Step 2: `apply_subagent_config` → SQLite subagent weights**

- [ ] **Step 3: Orchestrator.optimize() batch apply with confidence threshold**

- [ ] **Step 4: Commit**

---

### Task 7: EvalRunner + eval_set.yaml

**Files:**
- Create: `backend/tars/evolution/eval_runner.py`
- Create: `backend/tests/evolution/eval_set.yaml`
- Create: `backend/tests/test_evolution_eval_runner.py`

- [ ] **Step 1: Define ≥20 scenarios (personality_match, tool_choice, skill_route, subagent_delegate)**

- [ ] **Step 2: `pytest -m evolution_eval` marker**

- [ ] **Step 3: `EvalRunner.compare(before, after)` — rollback if drop >5%**

- [ ] **Step 4: Document B2 threshold ≥10% improvement in test README**

- [ ] **Step 5: Commit**

---

### Task 8: Coverage + EVOLUTION_GUIDE

**Files:**
- Update: `EVOLUTION_GUIDE.md`
- All test files

- [ ] **Step 1: Run coverage**

Run: `pytest backend/tests/test_evolution*.py --cov=tars.evolution --cov-report=term-missing`
Expected: ≥60% line coverage on `tars/evolution/`

- [ ] **Step 2: Update EVOLUTION_GUIDE — remove false claims, document ApplyEngine/rollback/eval gate**

- [ ] **Step 3: Commit**

---

## Spec Coverage

| Requirement | Task |
|-------------|------|
| A1 writeback | 2, 6 |
| A2 auto trigger | 3 |
| A3 audit diff | 2 |
| A4 tests ≥60% | 8 |
| A5 docs | 8 |
| B1–B4 eval | 7 |
| Feedback A/B/C/D | 1, 3, 4, 5 |

---

## Execution Handoff

**12–15 person-days**, 8 tasks. Run after Phase 1 Task 6+ (Insight feedback) or stub Insight hook.

**Options:** Subagent-driven (1) or inline (2).
