#!/usr/bin/env python3
"""Normalize doc footers to v4.3.2 platform alignment line."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FOOTER = (
    "\n\n---\n\n"
    "*平台文档对齐: TARS v4.3.2 · 见 [VERSION.md]({rel}) · 更新: 2026-05-26*\n"
)

FOOTER_PATTERNS = [
    re.compile(r"\n---\n\n\*文档版本:.*\*\s*$", re.S),
    re.compile(r"\n---\n\n\*平台文档对齐:.*\*\s*$", re.S),
    re.compile(r"\n\*文档版本: v[\d.]+.*\*\s*$", re.S),
    re.compile(r"\n\*\*文档版本\*\*:.*$", re.S),
]

# (path from repo root, relative path to VERSION.md)
TARGETS: list[tuple[str, str]] = [
    ("docs/04-运维文档/deployment.md", "../01-项目概览/VERSION.md"),
    ("docs/04-运维文档/insightforge-deploy.md", "../01-项目概览/VERSION.md"),
    ("docs/04-运维文档/insightforge-databases.md", "../01-项目概览/VERSION.md"),
    ("docs/04-运维文档/data-copilot-user-guide.md", "../01-项目概览/VERSION.md"),
    ("docs/04-运维文档/channels-architecture.md", "../01-项目概览/VERSION.md"),
    ("docs/04-运维文档/auth-model.md", "../01-项目概览/VERSION.md"),
    ("docs/PROVIDER_PLUGIN_GUIDE.md", "01-项目概览/VERSION.md"),
    ("docs/SECURITY_GUIDE.md", "01-项目概览/VERSION.md"),
    ("docs/01-项目概览/changelog.md", "VERSION.md"),
    ("EVOLUTION_GUIDE.md", "docs/01-项目概览/VERSION.md"),
    ("CRONJOB_GUIDE.md", "docs/01-项目概览/VERSION.md"),
    ("docs/SKILL_AUTHORING.md", "01-项目概览/VERSION.md"),
    ("docs/UPGRADE_GUIDE_v4.3.2.md", "01-项目概览/VERSION.md"),
]


def strip_old_footer(text: str) -> str:
    for pat in FOOTER_PATTERNS:
        text = pat.sub("", text)
    return text.rstrip() + "\n"


def main() -> None:
    for rel, version_rel in TARGETS:
        path = ROOT / rel
        if not path.exists():
            print(f"skip missing: {rel}")
            continue
        text = strip_old_footer(path.read_text(encoding="utf-8"))
        if "平台文档对齐" not in text:
            text = text.rstrip() + FOOTER.format(rel=version_rel)
        else:
            text = strip_old_footer(text) + FOOTER.format(rel=version_rel)
        path.write_text(text, encoding="utf-8")
        print(f"footer: {rel}")


if __name__ == "__main__":
    main()
