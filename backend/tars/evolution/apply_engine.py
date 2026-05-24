"""Evolution writeback engine with audit + rollback."""
from __future__ import annotations

import hashlib
import re
import uuid
from pathlib import Path
from typing import Dict, Optional

from ..database.base import Database, get_local_now
from ..workspace.soul import SoulParameters, parse_soul_markdown
from .models import ApplyRecord


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
    def __init__(self, db: Database, workspace_base: str = "~/.tars/workspaces"):
        self.db = db
        self.workspace_base = Path(workspace_base).expanduser()

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
        self.db.insert_evolution_apply_log(
            apply_id=apply_id,
            tenant_id=tenant_id,
            target_type=record.target_type,
            target_path=record.target_path,
            before_hash=record.before_hash,
            after_hash=record.after_hash,
            before_content=before,
            diff_summary=record.diff_summary,
            status="applied",
            created_at=now,
        )
        return record

    def apply_prompt(self, tenant_id: str, prompt_type: str, content: str) -> ApplyRecord:
        prompt_dir = self.workspace_base / tenant_id / "prompts"
        prompt_dir.mkdir(parents=True, exist_ok=True)
        prompt_path = prompt_dir / f"{prompt_type}.md"
        before = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""
        apply_id = str(uuid.uuid4())
        now = get_local_now().isoformat()
        prompt_path.write_text(content, encoding="utf-8")
        record = ApplyRecord(
            id=apply_id,
            tenant_id=tenant_id,
            target_type="prompt",
            target_path=str(prompt_path),
            before_hash=_file_hash(before),
            after_hash=_file_hash(content),
            diff_summary=f"prompt {prompt_type}",
        )
        self.db.insert_evolution_apply_log(
            apply_id=apply_id,
            tenant_id=tenant_id,
            target_type=record.target_type,
            target_path=record.target_path,
            before_hash=record.before_hash,
            after_hash=record.after_hash,
            before_content=before,
            diff_summary=record.diff_summary,
            status="applied",
            created_at=now,
        )
        return record

    def rollback(self, apply_id: str) -> bool:
        log = self.db.get_evolution_apply_log(apply_id)
        if not log or not log.get("before_content"):
            return False
        path = Path(log["target_path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(log["before_content"], encoding="utf-8")
        return True

    def read_personality_params(self, tenant_id: str) -> Dict[str, float]:
        soul_path = self._tenant_soul_path(tenant_id)
        soul = parse_soul_markdown(soul_path.read_text(encoding="utf-8"))
        p = soul.parameters
        return {
            k: getattr(p, k)
            for k in SoulParameters.__dataclass_fields__
        }
