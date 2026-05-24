"""One-time migration from legacy ~/.tars/workspaces to ~/.tars/agents."""
from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

LEGACY_ROOT = Path.home() / ".tars" / "workspaces"
AGENTS_ROOT = Path.home() / ".tars" / "agents"


def migrate_legacy_workspace(*, force: bool = False) -> List[str]:
    """Copy tenant SOUL/prompts/subagents from workspaces → agents if missing."""
    if not LEGACY_ROOT.exists():
        return []

    migrated: List[str] = []
    for tenant_dir in sorted(LEGACY_ROOT.iterdir()):
        if not tenant_dir.is_dir():
            continue
        dest = AGENTS_ROOT / tenant_dir.name
        dest.mkdir(parents=True, exist_ok=True)

        for filename in ("SOUL.md", "subagents.json"):
            src = tenant_dir / filename
            if not src.is_file():
                continue
            dst = dest / filename
            if dst.exists() and not force:
                continue
            shutil.copy2(src, dst)
            migrated.append(str(dst))
            logger.info("Evolution migration: %s → %s", src, dst)

        prompts_src = tenant_dir / "prompts"
        if prompts_src.is_dir():
            prompts_dest = dest / "prompts"
            prompts_dest.mkdir(parents=True, exist_ok=True)
            for prompt_file in sorted(prompts_src.glob("*.md")):
                dst_file = prompts_dest / prompt_file.name
                if dst_file.exists() and not force:
                    continue
                shutil.copy2(prompt_file, dst_file)
                migrated.append(str(dst_file))
                logger.info("Evolution migration: %s → %s", prompt_file, dst_file)

    if migrated:
        logger.warning(
            "Evolution 已从 %s 迁移 %d 个文件到 %s",
            LEGACY_ROOT,
            len(migrated),
            AGENTS_ROOT,
        )
    return migrated
