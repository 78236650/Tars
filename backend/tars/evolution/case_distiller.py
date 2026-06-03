"""CaseDistiller — cluster agent cases and distill them into reusable SKILL.md files.

Triggered by EvolutionOrchestrator.optimize() when enough undistilled cases
have accumulated.  Uses the LLM provider to generate skill frontmatter + body
and writes the result into skills/tenants/{tenant_id}/evolved-{name}/SKILL.md.
"""

from __future__ import annotations

import json
import logging
import os
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from .case_models import AgentCase, CaseSummary

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Distillation prompt — sent to the LLM to produce a SKILL.md
# ---------------------------------------------------------------------------
DISTILL_PROMPT = """你是一个 Agent 技能设计师。根据以下 Agent 成功执行的任务轨迹，提炼出一个可复用的技能 SKILL.md。

## 任务轨迹（同类任务的成功案例）

{cases_text}

## 要求

生成一个 SKILL.md 文件，格式为：

```
---
name: {skill_name}
description: {short_description}
triggers:
  - intent:{intent}
  - regex:{regex_pattern}
skip_when:
  - intent:general.chat
priority: {priority}
evolved: true
---

# {skill_name}

{markdown_body}
```

规则：
1. **name** — 用英文小写+下划线（如 "deploy_to_production"），需唯一
2. **description** — 一句话描述这个技能做什么（中文，≤80字）
3. **triggers** — 至少一个 intent: 触发标签（从 {intent_options} 中选择最匹配的）+ 一个 regex: 正则模式
4. **skip_when** — 默认保留 "intent:general.chat"
5. **priority** — 60-90 之间，按任务频率推算（默认 70）
6. **evolved: true** — 必须保留此标记，表示自动生成
7. **markdown_body** — 2-4 段的操作指南，包含：
   - 这个技能的执行流程（从案例中总结的模式）
   - 需要调用哪些工具（按顺序）
   - 常见陷阱/注意事项
   - 成功指标

只输出 SKILL.md 内容，不要额外解释。"""

INTENT_OPTIONS = [
    "coding.generate",
    "coding.explain",
    "coding.debug",
    "coding.refactor",
    "coding.review",
    "data.query",
    "data.analyze",
    "data.visualize",
    "deploy.release",
    "deploy.config",
    "ops.monitor",
    "ops.troubleshoot",
    "research.search",
    "research.synthesize",
    "writing.draft",
    "writing.edit",
    "task.planning",
    "task.automation",
    "general.qa",
    "general.chat",
]


class CaseDistiller:
    """Cluster undistilled cases and generate SKILL.md via LLM."""

    def __init__(
        self,
        db,
        case_capture,  # CaseCapture instance
        *,
        provider=None,  # LLM provider (set after agent init)
        skills_root: str = "",
        min_cases_per_cluster: int = 5,
        max_skills_per_run: int = 3,
        max_cases_per_skill: int = 30,
        approval_required: bool = True,
    ):
        self._db = db
        self.capture = case_capture
        self.provider = provider
        self.skills_root = Path(skills_root) if skills_root else Path(__file__).resolve().parents[3] / "skills"
        self.min_cases_per_cluster = min_cases_per_cluster
        self.max_skills_per_run = max_skills_per_run
        self.max_cases_per_skill = max_cases_per_skill
        self.approval_required = approval_required

    # ------------------------------------------------------------------
    # main entry point
    # ------------------------------------------------------------------
    def run(self, tenant_id: str = "default") -> Dict[str, Any]:
        """Full distillation cycle for one tenant.

        Returns summary dict with generated_skills, cases_distilled, etc.
        """
        result: Dict[str, Any] = {
            "tenant_id": tenant_id,
            "generated_skills": [],
            "cases_distilled": 0,
            "skipped": False,
            "reason": "",
        }

        if not self.provider:
            result["skipped"] = True
            result["reason"] = "no_llm_provider"
            return result

        pending = self.capture.get_pending_cases(
            tenant_id=tenant_id, min_success=True, limit=200
        )
        if len(pending) < self.min_cases_per_cluster:
            result["skipped"] = True
            result["reason"] = f"insufficient_cases ({len(pending)} < {self.min_cases_per_cluster})"
            return result

        # ------------------------------------------------------------------
        # 1. Cluster cases by task_description similarity (keyword-based)
        # ------------------------------------------------------------------
        clusters = self._cluster_cases(pending)

        # 2. Filter clusters that meet the minimum size
        viable = [
            c for c in clusters if c.case_count >= self.min_cases_per_cluster
        ]
        viable.sort(key=lambda c: c.success_rate * c.case_count, reverse=True)

        if not viable:
            result["skipped"] = True
            result["reason"] = f"no_viable_clusters ({len(clusters)} clusters, all < {self.min_cases_per_cluster})"
            return result

        # 3. Distill each viable cluster (up to max_skills_per_run)
        generated = 0
        for summary in viable[: self.max_skills_per_run]:
            # Re-fetch the full cases for this cluster
            cluster_cases = [
                c for c in pending
                if c.case_id in summary.sample_case_ids
                or any(kw in c.task_description.lower() for kw in summary.representative_tasks)
            ][: self.max_cases_per_skill]

            if len(cluster_cases) < self.min_cases_per_cluster:
                continue

            try:
                skill_path = self._distill_cluster(tenant_id, summary, cluster_cases)
                if skill_path:
                    # Mark cases as distilled
                    distilled_ids = [c.case_id for c in cluster_cases]
                    self.capture.mark_distilled(distilled_ids)
                    result["generated_skills"].append(str(skill_path))
                    result["cases_distilled"] += len(distilled_ids)
                    generated += 1
            except Exception as exc:
                logger.exception(
                    "distill cluster failed tenant=%s cluster=%s",
                    tenant_id,
                    summary.task_description[:60],
                )

        if not result["generated_skills"]:
            result["skipped"] = True
            result["reason"] = "distillation_produced_no_skills"

        return result

    # ------------------------------------------------------------------
    # clustering
    # ------------------------------------------------------------------
    def _cluster_cases(self, cases: List[AgentCase]) -> List[CaseSummary]:
        """Keyword-based clustering of task descriptions.

        Uses a simple bag-of-keywords approach: cases that share ≥2
        significant keywords are grouped together.  This is intentionally
        lightweight — the LLM handles semantic refinement during distillation.
        """
        # Extract significant keywords per case
        STOP_WORDS = {
            "的", "是", "了", "在", "和", "我", "要", "想", "帮", "请",
            "一个", "这个", "那个", "什么", "怎么", "如何", "可以",
            "the", "a", "an", "is", "are", "to", "for", "with",
            "and", "or", "in", "on", "of", "that", "this", "it",
        }
        import re

        case_keywords: List[List[str]] = []
        for c in cases:
            tokens = re.findall(r"[\w\u4e00-\u9fff]{2,}", c.task_description.lower())
            keywords = [t for t in tokens if t not in STOP_WORDS][:10]
            case_keywords.append(keywords)

        # Union-find clustering
        n = len(cases)
        parent = list(range(n))

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: int, b: int) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        for i in range(n):
            for j in range(i + 1, n):
                common = set(case_keywords[i]) & set(case_keywords[j])
                if len(common) >= 2:
                    union(i, j)

        # Collect clusters
        cluster_map: Dict[int, List[int]] = defaultdict(list)
        for i in range(n):
            cluster_map[find(i)].append(i)

        summaries: List[CaseSummary] = []
        for indices in cluster_map.values():
            cluster_cases = [cases[i] for i in indices]
            success_count = sum(1 for c in cluster_cases if c.success)

            # Common tools across the cluster
            tool_freq: Dict[str, int] = defaultdict(int)
            for c in cluster_cases:
                for t in c.tools_used:
                    tool_freq[t] += 1
            common_tools = sorted(tool_freq, key=tool_freq.get, reverse=True)[:5]

            # Representative tasks (the 3 most recent)
            sorted_cases = sorted(cluster_cases, key=lambda c: c.created_at, reverse=True)
            rep_tasks = [c.task_description[:120] for c in sorted_cases[:3]]
            sample_ids = [c.case_id for c in sorted_cases[: self.max_cases_per_skill]]

            # Use the most successful case's description as the cluster label
            best_case = max(cluster_cases, key=lambda c: c.feedback_score)
            label = best_case.task_description[:80]

            summaries.append(
                CaseSummary(
                    task_description=label,
                    case_count=len(cluster_cases),
                    success_count=success_count,
                    common_tools=common_tools,
                    sample_case_ids=sample_ids,
                    representative_tasks=rep_tasks,
                )
            )

        return summaries

    # ------------------------------------------------------------------
    # distillation
    # ------------------------------------------------------------------
    def _distill_cluster(
        self,
        tenant_id: str,
        summary: CaseSummary,
        cluster_cases: List[AgentCase],
    ) -> Optional[Path]:
        """Call LLM to generate a SKILL.md from a case cluster."""
        # Build the prompt
        cases_text = self._build_cases_text(cluster_cases)
        skill_name = self._derive_skill_name(summary)
        short_desc = summary.task_description[:80]
        intent = self._guess_intent(summary)
        regex_pattern = self._derive_regex(summary)
        priority = min(90, 60 + summary.case_count)

        prompt = DISTILL_PROMPT.format(
            cases_text=cases_text,
            skill_name=skill_name,
            short_description=short_desc,
            intent=intent,
            intent_options=", ".join(INTENT_OPTIONS),
            regex_pattern=regex_pattern,
            priority=priority,
        )

        # Call LLM
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                future = concurrent.futures.Future()

                async def _call():
                    try:
                        resp = await self.provider.complete(prompt, max_tokens=2000)
                        content = resp.content if hasattr(resp, "content") else str(resp)
                        future.set_result(content)
                    except Exception as e:
                        future.set_exception(e)

                loop.create_task(_call())
                skill_content = future.result(timeout=60)
            else:
                resp = loop.run_until_complete(
                    self.provider.complete(prompt, max_tokens=2000)
                )
                skill_content = resp.content if hasattr(resp, "content") else str(resp)
        except Exception as exc:
            logger.error("LLM call failed during distillation: %s", exc)
            return None

        if not skill_content or len(skill_content.strip()) < 50:
            logger.warning("Distillation produced empty/short output")
            return None

        # Ensure evolved: true is in the frontmatter
        skill_content = self._ensure_evolved_flag(skill_content)

        # Write to tenant skills directory
        skill_dir = self._tenant_skill_dir(tenant_id, skill_name)
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_md_path = skill_dir / "SKILL.md"
        skill_md_path.write_text(skill_content, encoding="utf-8")

        logger.info(
            "Distilled skill %s from %d cases → %s",
            skill_name,
            summary.case_count,
            skill_md_path,
        )
        return skill_md_path

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _build_cases_text(self, cases: List[AgentCase]) -> str:
        """Build a compact text representation of cases for the LLM prompt."""
        parts = []
        for i, c in enumerate(cases[:20], 1):  # cap at 20 to avoid prompt bloat
            parts.append(f"### Case {i}\n{c.summary_for_distillation()}")
        return "\n\n".join(parts)

    def _derive_skill_name(self, summary: CaseSummary) -> str:
        """Derive a machine-friendly skill name from the cluster label."""
        import re
        name = re.sub(r"[^\w\u4e00-\u9fff]+", "_", summary.task_description.lower())
        name = re.sub(r"_+", "_", name).strip("_")
        if len(name) > 40:
            name = name[:40]
        if not name:
            name = "evolved_skill"
        return name

    def _guess_intent(self, summary: CaseSummary) -> str:
        """Guess the most likely intent category from tools used."""
        tools_lower = [t.lower() for t in summary.common_tools]
        tool_set = set(tools_lower)

        data_tools = {"sql", "query", "chart", "bi", "datasource", "knowledge_search"}
        coding_tools = {"code", "python_exec", "shell", "command", "file_write"}
        deploy_tools = {"deploy", "git", "docker", "ssh"}
        research_tools = {"web_search", "web_fetch", "read_wiki"}
        planning_tools = {"task_planner", "task_executor", "orchestration"}

        if tool_set & data_tools:
            return "data.analyze"
        if tool_set & coding_tools:
            return "coding.generate"
        if tool_set & deploy_tools:
            return "deploy.release"
        if tool_set & research_tools:
            return "research.synthesize"
        if tool_set & planning_tools:
            return "task.planning"
        return "general.qa"

    def _derive_regex(self, summary: CaseSummary) -> str:
        """Derive a regex trigger from the common keywords in the cluster."""
        import re
        # Collect keywords from representative tasks
        all_tokens: List[str] = []
        for task in summary.representative_tasks:
            tokens = re.findall(r"[\w\u4e00-\u9fff]{2,}", task.lower())
            all_tokens.extend(tokens)

        # Pick top 3 by frequency
        from collections import Counter
        freq = Counter(all_tokens)
        top = [w for w, _ in freq.most_common(3) if len(w) >= 2]
        if top:
            return ".*(" + "|".join(top[:2]) + ").*"
        return ".*"

    def _ensure_evolved_flag(self, content: str) -> str:
        """Ensure 'evolved: true' is present in the YAML frontmatter."""
        if "evolved:" in content:
            return content
        # Insert after priority line or after description
        lines = content.split("\n")
        result = []
        inserted = False
        for i, line in enumerate(lines):
            result.append(line)
            if not inserted and line.strip().startswith("priority:"):
                result.append("evolved: true")
                inserted = True
        if not inserted:
            # Find end of frontmatter and insert there
            result = []
            in_frontmatter = False
            fm_end = -1
            for i, line in enumerate(lines):
                if line.strip() == "---":
                    if not in_frontmatter:
                        in_frontmatter = True
                    elif fm_end < 0:
                        fm_end = i
                result.append(line)
            if fm_end > 0:
                result.insert(fm_end, "evolved: true")
            else:
                result.append("evolved: true")
        return "\n".join(result)

    def _tenant_skill_dir(self, tenant_id: str, skill_name: str) -> Path:
        """Resolve the directory for a tenant's evolved skill."""
        safe_name = skill_name.replace("/", "-").replace(" ", "-")
        if tenant_id and tenant_id != "default":
            return self.skills_root / "tenants" / tenant_id / f"evolved-{safe_name}"
        return self.skills_root / "_global" / f"evolved-{safe_name}"
