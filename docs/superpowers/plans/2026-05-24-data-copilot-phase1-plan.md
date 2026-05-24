# TARS v4.2.0 — Phase 1: 内网数据/分析 Copilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship TARS v4.2.0 Phase 1 — internal data/analysis Copilot with module-separated entry, production-ready InsightForge gating, and knowledge↔metric bidirectional citations.

**Architecture:** Add `KnowledgeBridge` in the insight layer for prioritized KB retrieval and metric-card publishing; wire frontend `initSettings()` for module/role gating; introduce `business_analyst` role; extend `MetricAnswer` with structured citations consumed by existing citation UI.

**Tech Stack:** Python 3.11 / FastAPI / SQLite / Vue 3 / Pinia / pytest

**Spec:** [2026-05-24-data-copilot-phase1-design.md](../specs/2026-05-24-data-copilot-phase1-design.md)

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/tars/insight/knowledge_bridge.py` | Create | Layered KB retrieval + metric card publish |
| `backend/tars/insight/metric_answer.py` | Modify | Add `MetricCitation`, `citations` field |
| `backend/tars/insight/metric_qa_engine.py` | Modify | Call KnowledgeBridge in `ask()` |
| `backend/tars/insight/adoption_service.py` | Modify | Hook `publish_metric_card` after adopt |
| `backend/tars/insight/config.py` | Modify | `adoption.publish_to_knowledge`, `knowledge_bridge.timeout_ms` |
| `backend/config/insight.yaml` | Modify | New config keys |
| `backend/tars/gateway/role_template.py` | Modify | `business_analyst`; fix `insight_analyst` modules |
| `backend/tars/api/knowledge.py` | Modify | Accept `metric_ids` on upload |
| `backend/tars/knowledge/sqlite_store.py` | Modify | Store/read `metadata_json.metric_ids` |
| `backend/tars/main.py` | Modify | SSE workers startup warning |
| `backend/tests/test_insight_knowledge_bridge.py` | Create | Bridge unit tests |
| `backend/tests/test_insight_adopt_knowledge.py` | Create | Adopt→KB tests |
| `backend/tests/test_role_module_gating.py` | Modify/Create | business_analyst gating |
| `backend/tests/insight/eval_set.yaml` | Modify | +3–5 knowledge-context cases |
| `frontend/src/App.vue` | Modify | Call `initSettings()` |
| `frontend/src/components/settings/RoleEditor.vue` | Modify | Add `insight` to `allModules` |
| `frontend/src/components/layout/LeftPanel.vue` | Modify | Module subtitles |
| `frontend/src/components/insight/MetricAnswerCard.vue` | Modify | Render citations |
| `frontend/src/router/index.spec.ts` | Modify | Gating with role modules |
| `docs/04-运维文档/data-copilot-user-guide.md` | Create | User guide |
| `scripts/acceptance/phase1-data-copilot.sh` | Create | Manual acceptance |

---

### Task 1: Module gating — frontend initSettings

**Files:**
- Modify: `frontend/src/App.vue`
- Test: `frontend/src/App.spec.ts` (extend if exists)

- [ ] **Step 1: Write failing test**

In `frontend/src/App.spec.ts`, mock `settingsStore.initSettings` and assert it is called after `initAuth` when authenticated:

```typescript
it('calls initSettings after auth init', async () => {
  const initSettings = vi.fn().mockResolvedValue(undefined)
  vi.mocked(useSettingsStore).mockReturnValue({
    loadModels: vi.fn(),
    initSettings,
  } as any)
  // mount App, await onMounted
  expect(initSettings).toHaveBeenCalled()
})
```

- [ ] **Step 2: Run test — expect FAIL**

Run: `cd frontend && npm test -- App.spec.ts -v`

- [ ] **Step 3: Implement**

```typescript
// frontend/src/App.vue onMounted
await authStore.initAuth()
if (authStore.isAuthenticated) {
  await settingsStore.initSettings()
} else {
  await settingsStore.loadModels()
}
```

- [ ] **Step 4: Run test — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.vue frontend/src/App.spec.ts
git commit -m "fix(frontend): wire initSettings for module and role gating"
```

---

### Task 2: Role templates — business_analyst + insight_analyst fix

**Files:**
- Modify: `backend/tars/gateway/role_template.py`
- Test: `backend/tests/test_role_module_gating.py`

- [ ] **Step 1: Write failing test**

```python
def test_business_analyst_has_insight_not_bi(role_manager):
    t = role_manager.get("business_analyst")
    assert t is not None
    assert "insight" in t.allowed_modules
    assert "bi" not in t.allowed_modules

def test_insight_analyst_has_no_bi(role_manager):
    t = role_manager.get("insight_analyst")
    assert "insight" in t.allowed_modules
    assert "bi" not in t.allowed_modules
```

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest backend/tests/test_role_module_gating.py -v`

- [ ] **Step 3: Add template in `BUILTIN_TEMPLATES`**

```python
RoleTemplate(
    id="business_analyst",
    name="业务分析师",
    description="问数/口径/知识库，不含 BI SQL",
    is_builtin=True,
    allowed_tools=[
        "weather", "web_search", "web_fetch", "memory", "knowledge_search",
        "meeting_recognizer",
        "insight_get_workflow", "insight_list_sources", "insight_start_forge",
        "insight_profile_datasource", "insight_ask_metric", "insight_adopt_metric",
        "insight_explain_metric", "insight_give_feedback",
    ],
    denied_tools=["bi_query", "bi_generate_chart", "bi_list_datasources", "shell", "python_exec"],
    allowed_modules=["insight", "knowledge", "meeting", "skillhub"],
    workspace_restriction=True,
    max_concurrent=1,
),
```

Change `insight_analyst.allowed_modules` from `["bi", "knowledge", "insight"]` to `["knowledge", "insight"]`.

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Commit**

---

### Task 3: RoleEditor — add insight module

**Files:**
- Modify: `frontend/src/components/settings/RoleEditor.vue:31`
- Modify: `frontend/src/views/RolesView.vue` (if duplicate list)

- [ ] **Step 1: Change module list**

```typescript
const allModules = ['bi', 'knowledge', 'meeting', 'skillhub', 'insight']
```

- [ ] **Step 2: Verify RolesView editor shows insight checkbox**

Run: `cd frontend && npm test -- RolesView -v` (or manual UI check)

- [ ] **Step 3: Commit**

---

### Task 4: MetricCitation dataclass

**Files:**
- Modify: `backend/tars/insight/metric_answer.py`
- Test: `backend/tests/test_insight_knowledge_bridge.py` (partial)

- [ ] **Step 1: Write failing test**

```python
from tars.insight.metric_answer import MetricCitation, MetricAnswer

def test_metric_answer_serializes_citations():
    c = MetricCitation(doc_id="d1", title="GMV口径", snippet="不含退款", source_type="insight_glossary", relevance=0.9)
    ans = MetricAnswer(value=100, citations=[c])
    d = ans.to_dict()
    assert d["citations"][0]["doc_id"] == "d1"
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement**

```python
@dataclass
class MetricCitation:
    doc_id: str
    title: str
    snippet: str
    source_type: str  # insight_glossary | meeting_summary | metric_linked
    relevance: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

# In MetricAnswer:
citations: List[MetricCitation] = field(default_factory=list)

# In to_dict(): serialize citations list
```

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

---

### Task 5: KnowledgeBridge — retrieve_for_question

**Files:**
- Create: `backend/tars/insight/knowledge_bridge.py`
- Modify: `backend/tars/insight/config.py`, `backend/config/insight.yaml`
- Test: `backend/tests/test_insight_knowledge_bridge.py`

- [ ] **Step 1: Write failing tests for priority order**

```python
@pytest.mark.asyncio
async def test_retrieve_prefers_insight_collection_over_meeting(db, bridge, monkeypatch):
    calls = []
    def fake_search(tenant_id, query, collection_ids=None, top_k=3, **kw):
        calls.append(collection_ids)
        if collection_ids and collection_ids[0].startswith("insight_"):
            return [{"doc_id": "insight-doc", "title": "说明书", "content": "GMV定义", "score": 0.95}]
        return [{"doc_id": "meet-doc", "title": "会议", "content": "...", "score": 0.5}]
    monkeypatch.setattr("tars.insight.knowledge_bridge.search_knowledge", fake_search)
    citations = await bridge.retrieve_for_question("tenant1", "ds-1", "GMV口径是什么")
    assert citations[0].doc_id == "insight-doc"
    assert citations[0].source_type == "insight_glossary"
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement `KnowledgeBridge`**

Key methods:
- `collection_id_for(datasource_id) -> f"insight_{datasource_id}"`
- `async retrieve_for_question(tenant_id, datasource_id, question, metric_key=None) -> List[MetricCitation]`
  - Step 1: `search_knowledge(..., collection_ids=[insight_col], top_k=3)`
  - Step 2: meeting collections from config `insight.knowledge_bridge.meeting_collection_prefixes: ["meeting_"]`
  - Step 3: if metric_key: query docs with metadata filter (sqlite_store helper)
  - dedupe by doc_id, truncate snippets to ~200 chars, total ~1500 tokens
  - wrap in `asyncio.wait_for(..., timeout=config.knowledge_bridge.timeout_ms/1000)` → return [] on timeout

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Commit**

---

### Task 6: Wire KnowledgeBridge into MetricQaEngine

**Files:**
- Modify: `backend/tars/insight/metric_qa_engine.py`
- Test: extend `backend/tests/test_insight_knowledge_bridge.py`

- [ ] **Step 1: Write integration test** — mock bridge, assert `MetricAnswer.citations` populated after `ask()`

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: In `MetricQaEngine.__init__` add optional `knowledge_bridge: KnowledgeBridge | None`**

In `ask()`, after route decision, before building answer:

```python
citations = []
if self._knowledge_bridge:
    try:
        citations = await self._knowledge_bridge.retrieve_for_question(
            tenant_id, datasource_id, question, metric_key=decision.metric_key
        )
    except asyncio.TimeoutError:
        logger.warning("knowledge bridge timeout, skipping")
# inject citations into definition/reasoning text for LLM branches
answer.citations = citations
```

- [ ] **Step 4: Register bridge in `insight/api/router.py` init**

- [ ] **Step 5: Run insight tests — expect PASS**

Run: `pytest backend/tests/test_insight_knowledge_bridge.py backend/tests/test_insight_module.py -v`

- [ ] **Step 6: Commit**

---

### Task 7: Adoption → publish_metric_card

**Files:**
- Modify: `backend/tars/insight/adoption_service.py`
- Modify: `backend/config/insight.yaml` — `adoption.publish_to_knowledge: true`
- Test: `backend/tests/test_insight_adopt_knowledge.py`

- [ ] **Step 1: Write failing test** — after adopt, assert KB document contains metric_key

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Add `KnowledgeBridge.publish_metric_card(datasource_id, metric, tenant_id)`**

Append markdown section to `insight_{datasource_id}` collection via `KnowledgePublisher` pattern; set `metadata_json.metric_ids`.

In `AdoptionService.adopt()` after successful adopt:

```python
if self.config.adoption.publish_to_knowledge and self._knowledge_bridge:
    try:
        self._knowledge_bridge.publish_metric_card(...)
    except Exception as e:
        logger.warning("publish_metric_card failed: %s", e)
        self._audit(..., "knowledge_publish_failed", ...)
```

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

---

### Task 8: Document upload metric_ids

**Files:**
- Modify: `backend/tars/api/knowledge.py`
- Modify: `backend/tars/knowledge/sqlite_store.py`
- Test: `backend/tests/test_vector_search_knowledge_base.py` (extend)

- [ ] **Step 1: Test upload with Form field `metric_ids=uuid1,uuid2` persists in metadata**

- [ ] **Step 2: Implement** — parse JSON/comma list → `metadata_json={"metric_ids": [...]}`

- [ ] **Step 3: Add sqlite_store helper `search_docs_by_metric_id(tenant_id, metric_id, top_k)`**

- [ ] **Step 4: Wire into KnowledgeBridge Step 3**

- [ ] **Step 5: Commit**

---

### Task 9: Frontend — MetricAnswerCard citations

**Files:**
- Modify: `frontend/src/components/insight/MetricAnswerCard.vue`
- Reuse: `frontend/src/components/chat/KnowledgeCitationPanel.vue`

- [ ] **Step 1: Extend props/types for `citations: MetricCitation[]`**

- [ ] **Step 2: Render chips** — `[ref:doc_id|title]` pattern matching ChatView

- [ ] **Step 3: Click opens KnowledgeCitationPanel**

- [ ] **Step 4: Manual verify on /insight ask flow**

- [ ] **Step 5: Commit**

---

### Task 10: LeftPanel subtitles + user guide

**Files:**
- Modify: `frontend/src/components/layout/LeftPanel.vue`
- Modify: `frontend/src/i18n/index.ts`
- Create: `docs/04-运维文档/data-copilot-user-guide.md`

- [ ] **Step 1: Add i18n keys**

```typescript
'nav.insight.subtitle': '问指标 / 口径',
'nav.bi.subtitle': 'SQL / 图表',
```

- [ ] **Step 2: Show subtitle under nav labels when not collapsed**

- [ ] **Step 3: Write user guide** — business path vs engineer path tables from spec §2.4

- [ ] **Step 4: Commit**

---

### Task 11: SSE startup warning

**Files:**
- Modify: `backend/tars/main.py` or `backend/tars/insight/api/router.py`

- [ ] **Step 1: On startup, if `WEB_CONCURRENCY` or uvicorn workers > 1 and no sticky hint env, log ERROR with link to `docs/04-运维文档/insightforge-deploy.md`**

- [ ] **Step 2: Commit**

---

### Task 12: Eval extension + acceptance script

**Files:**
- Modify: `backend/tests/insight/eval_set.yaml`
- Create: `scripts/acceptance/phase1-data-copilot.sh`

- [ ] **Step 1: Add 3 eval cases** with `expect_citations: true` and seeded KB fixtures in conftest

- [ ] **Step 2: Run eval**

Run: `pytest backend/tests/insight/test_insight_eval.py -m insight_eval -v`
Expected: ≥80% pass rate

- [ ] **Step 3: Write acceptance shell script** — curl login as business_analyst + analyst roles, hit `/api/insight/ask`, assert JSON `citations` length

- [ ] **Step 4: Commit**

---

## Spec Coverage Checklist

| Spec requirement | Task |
|------------------|------|
| A: initSettings + gating | Task 1, 2, 3 |
| A: SSE deploy warning | Task 11 |
| B: BI/Insight boundary doc | Task 10 |
| B: nav guidance | Task 10 |
| C: KnowledgeBridge B | Task 5, 6 |
| C: Adoption publish C | Task 7, 8 |
| Citations UI | Task 9 |
| Eval ≥80% + 3–5 cases | Task 12 |
| business_analyst role | Task 2 |

---

## Execution Handoff

Plan complete. Recommended: **subagent-driven-development** (one task per subagent with review between tasks).

Estimated: **8 person-days**, **12 tasks**.
