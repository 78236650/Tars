"""Evolution writeback engine with audit + rollback."""
from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from ..database.base import Database, get_local_now
from ..workspace.soul import SoulParameters, parse_soul_markdown
from .models import ApplyRecord

logger = logging.getLogger(__name__)
LEGACY_EVOLUTION_BASE = Path("~/.tars/workspaces").expanduser()
DEFAULT_EVOLUTION_BASE = Path("~/.tars/agents").expanduser()

TUNED_START = "<!-- tars-evolution: tuned -->"
TUNED_END = "<!-- /tars-evolution -->"


class RollbackConflictError(Exception):
    """Current file content does not match expected after_hash."""


class PromptDiffTooLarge(Exception):
    """Tuned prompt block exceeds configured size limit."""


def _file_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _patch_soul_parameters(content: str, params: Dict[str, float]) -> str:
    lines = content.splitlines()
    out: list[str] = []
    in_params = False
    seen_keys: set[str] = set()
    for line in lines:
        if line.strip().lower().startswith("## parameters"):
            in_params = True
            out.append(line)
            continue
        if in_params and line.startswith("## "):
            for key, val in params.items():
                if key not in seen_keys:
                    out.append(f"- {key}: {val}")
                    seen_keys.add(key)
            in_params = False
            out.append(line)
            continue
        if in_params and line.strip().startswith("-") and ":" in line:
            key = line.split(":", 1)[0].lstrip("- ").strip()
            if key in params:
                out.append(f"- {key}: {params[key]}")
                seen_keys.add(key)
                continue
        out.append(line)
    if in_params:
        for key, val in params.items():
            if key not in seen_keys:
                out.append(f"- {key}: {val}")
    return "\n".join(out) + ("\n" if content.endswith("\n") else "")


class ApplyEngine:
    def __init__(self, db: Database, workspace_base: str = "~/.tars/agents"):
        self.db = db
        self.workspace_base = Path(workspace_base).expanduser()
        self._batch_id: Optional[str] = None
        if (
            LEGACY_EVOLUTION_BASE.exists()
            and LEGACY_EVOLUTION_BASE != self.workspace_base
            and any(LEGACY_EVOLUTION_BASE.iterdir())
        ):
            logger.warning(
                "检测到旧 Evolution 写回目录 %s；当前使用 %s。"
                "请运行 scripts/migrate-evolution-workspace.sh 完成迁移。",
                LEGACY_EVOLUTION_BASE,
                self.workspace_base,
            )

    def begin_batch(self) -> str:
        self._batch_id = str(uuid.uuid4())
        return self._batch_id

    def _persist_apply_log(self, record: ApplyRecord, before_content: str, *, created_at: str) -> None:
        self.db.insert_evolution_apply_log(
            apply_id=record.id,
            tenant_id=record.tenant_id,
            target_type=record.target_type,
            target_path=record.target_path,
            before_hash=record.before_hash,
            after_hash=record.after_hash,
            before_content=before_content,
            diff_summary=record.diff_summary,
            status="applied",
            created_at=created_at,
            batch_id=self._batch_id,
        )

    @staticmethod
    def _merge_tuned_block(before: str, tuned: str, max_chars: int) -> str:
        tuned_body = tuned.strip()
        if len(tuned_body) > max_chars:
            raise PromptDiffTooLarge(f"tuned block {len(tuned_body)} chars exceeds limit {max_chars}")
        block = f"{TUNED_START}\n{tuned_body}\n{TUNED_END}"
        if TUNED_START in before:
            pattern = rf"{re.escape(TUNED_START)}.*?{re.escape(TUNED_END)}"
            return re.sub(pattern, block, before, count=1, flags=re.DOTALL)
        base = before.rstrip()
        return f"{base}\n\n{block}\n" if base else f"{block}\n"

    def _tenant_soul_path(self, tenant_id: str) -> Path:
        path = self.workspace_base / tenant_id / "SOUL.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            default = """# TARS SOUL

## Identity
- Name: TARS
- Role: AI Agent

## Parameters
- honesty: 0.9
- humor: 0.5
- initiative: 0.7
- empathy: 0.7

## Communication Style
- 简洁专业

## Behavior Rules
1. 诚实回答
"""
            path.write_text(default, encoding="utf-8")
        return path

    def apply_personality(self, tenant_id: str, params: Dict[str, float]) -> ApplyRecord:
        soul_path = self._tenant_soul_path(tenant_id)
        before = soul_path.read_text(encoding="utf-8")
        after = _patch_soul_parameters(before, params)
        apply_id = str(uuid.uuid4())
        now = get_local_now().isoformat()
        soul_path.write_text(after, encoding="utf-8")
        record = ApplyRecord(
            id=apply_id,
            tenant_id=tenant_id,
            target_type="personality",
            target_path=str(soul_path),
            before_hash=_file_hash(before),
            after_hash=_file_hash(after),
            diff_summary=f"updated {len(params)} parameters",
        )
        self._persist_apply_log(record, before, created_at=now)
        return record

    def apply_prompt(self, tenant_id: str, prompt_type: str, content: str) -> ApplyRecord:
        from .config import get_evolution_config

        prompt_dir = self.workspace_base / tenant_id / "prompts"
        prompt_dir.mkdir(parents=True, exist_ok=True)
        prompt_path = prompt_dir / f"{prompt_type}.md"
        before = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""
        max_chars = get_evolution_config().prompt_writeback.max_tuned_chars
        after = self._merge_tuned_block(before, content, max_chars)
        apply_id = str(uuid.uuid4())
        now = get_local_now().isoformat()
        prompt_path.write_text(after, encoding="utf-8")
        record = ApplyRecord(
            id=apply_id,
            tenant_id=tenant_id,
            target_type="prompt",
            target_path=str(prompt_path),
            before_hash=_file_hash(before),
            after_hash=_file_hash(after),
            diff_summary=f"prompt {prompt_type}",
        )
        self._persist_apply_log(record, before, created_at=now)
        return record

    def _subagent_config_path(self, tenant_id: str) -> Path:
        path = self.workspace_base / tenant_id / "subagents.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def read_subagent_config(self, tenant_id: str) -> Dict[str, Any]:
        path = self._subagent_config_path(tenant_id)
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def resolve_skill_md_path(self, skill_id: str) -> Optional[str]:
        conn = self.db._get_conn()
        try:
            row = conn.execute(
                "SELECT dir_path FROM skills_v3 WHERE id = ?",
                (skill_id,),
            ).fetchone()
        except Exception:
            return None
        if not row or not row[0]:
            return None
        skill_md = Path(row[0]) / "SKILL.md"
        return str(skill_md) if skill_md.exists() else None

    def apply_subagent_config(self, tenant_id: str, config: Dict[str, Any]) -> ApplyRecord:
        path = self._subagent_config_path(tenant_id)
        before = path.read_text(encoding="utf-8") if path.exists() else ""
        merged = {**self.read_subagent_config(tenant_id), **config}
        after = json.dumps(merged, ensure_ascii=False, indent=2)
        apply_id = str(uuid.uuid4())
        now = get_local_now().isoformat()
        path.write_text(after, encoding="utf-8")
        record = ApplyRecord(
            id=apply_id,
            tenant_id=tenant_id,
            target_type="subagent_config",
            target_path=str(path),
            before_hash=_file_hash(before),
            after_hash=_file_hash(after),
            diff_summary=f"subagent keys: {', '.join(sorted(config.keys()))}",
        )
        self._persist_apply_log(record, before, created_at=now)
        return record

    def read_prompt(self, tenant_id: str, prompt_type: str) -> str:
        prompt_path = self.workspace_base / tenant_id / "prompts" / f"{prompt_type}.md"
        if not prompt_path.exists():
            return ""
        return prompt_path.read_text(encoding="utf-8")

    def rollback(self, apply_id: str, *, force: bool = False) -> bool:
        log = self.db.get_evolution_apply_log(apply_id)
        if not log:
            return False
        before_content = log.get("before_content")
        if before_content is None:
            return False
        path = Path(log["target_path"])
        if path.exists():
            current = path.read_text(encoding="utf-8")
            expected_after = log.get("after_hash")
            if expected_after and _file_hash(current) != expected_after and not force:
                raise RollbackConflictError(f"rollback conflict for {apply_id}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(before_content, encoding="utf-8")
        return True

    def rollback_batch(self, batch_id: str, *, force: bool = False) -> list[str]:
        rolled_back: list[str] = []
        for log in self.db.list_evolution_apply_logs_by_batch(batch_id):
            apply_id = log["id"]
            try:
                if self.rollback(apply_id, force=force):
                    rolled_back.append(apply_id)
            except RollbackConflictError:
                logger.warning("Skip rollback apply_id=%s due to conflict", apply_id)
        return rolled_back

    def apply_skill_description(
        self,
        tenant_id: str,
        skill_id: str,
        description: str,
        *,
        skill_md_path: Optional[str] = None,
    ) -> ApplyRecord:
        path = Path(skill_md_path) if skill_md_path else None
        before = ""
        after = description
        if path and path.exists():
            before = path.read_text(encoding="utf-8")
            if re.search(r"(?m)^description:\s*.+$", before):
                after = re.sub(
                    r"(?m)^description:\s*.+$",
                    f"description: {description}",
                    before,
                    count=1,
                )
            else:
                after = f"---\ndescription: {description}\n---\n\n{before}"
            path.write_text(after, encoding="utf-8")
        apply_id = str(uuid.uuid4())
        now = get_local_now().isoformat()
        target = str(path) if path else f"skill:{skill_id}"
        record = ApplyRecord(
            id=apply_id,
            tenant_id=tenant_id,
            target_type="skill_description",
            target_path=target,
            before_hash=_file_hash(before),
            after_hash=_file_hash(after),
            diff_summary=f"skill {skill_id} description",
        )
        self._persist_apply_log(record, before, created_at=now)
        return record

    def read_personality_params(self, tenant_id: str) -> Dict[str, float]:
        soul_path = self._tenant_soul_path(tenant_id)
        soul = parse_soul_markdown(soul_path.read_text(encoding="utf-8"))
        p = soul.parameters
        return {
            k: getattr(p, k)
            for k in SoulParameters.__dataclass_fields__
        }
