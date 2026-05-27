#!/usr/bin/env python3
"""Add status frontmatter to docs/superpowers/**/*.md (idempotent)."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SP = ROOT / "docs" / "superpowers"

PLATFORM_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"skill-routing|llm-wiki", re.I), "4.3.2"),
    (re.compile(r"knowledge-deep-ingest", re.I), "4.3.1"),
    (re.compile(r"openclaw-phase3|v4\.3\.0-fix", re.I), "4.3.0"),
    (re.compile(r"data-copilot|evolution-phase2|memory-tree-v4\.2", re.I), "4.2.0"),
    (re.compile(r"insightforge-profile-perf", re.I), "4.3.1"),
    (re.compile(r"insightforge-ins-2|ins-2-redesign", re.I), "4.2.0"),
    (re.compile(r"insightforge-design", re.I), "4.2.0"),
    (re.compile(r"v4\.1\.0|memory-tree-entity|memory-tree-entity-view", re.I), "4.1.4"),
    (
        re.compile(
            r"v4\.0\.|tars-v4\.0|phase1-security|phase2-performance|phase3-provider|"
            r"phase4-platform|workspace-isolation|admin-role|default-admin",
            re.I,
        ),
        "4.0.0",
    ),
    (re.compile(r"fix-plan|fix-baseline", re.I), "4.3.0"),
]

SUPERSEDED_PATTERNS = re.compile(
    r"task-automation-design-original|task-automation-v1\.[45]|"
    r"skills-pdca-workspace-fusion-v1\.0|task-automation-v2\.4",
    re.I,
)


def platform_version(name: str) -> str:
    for pat, ver in PLATFORM_RULES:
        if pat.search(name):
            return ver
    return "4.0.0"


def doc_status(name: str, text: str) -> str:
    if SUPERSEDED_PATTERNS.search(name):
        return "superseded"
    head = text[:800]
    if re.search(r"草案|待审|Draft — 待", head, re.I) and "已交付" not in head and "shipped" not in head:
        if not re.search(r"skill-routing|llm-wiki|knowledge-deep-ingest", name, re.I):
            return "draft"
    return "shipped"


def has_status_frontmatter(text: str) -> bool:
    if not text.startswith("---"):
        return False
    end = text.find("\n---", 3)
    if end == -1:
        return False
    block = text[3:end]
    return "status:" in block


def build_frontmatter(path: Path, text: str) -> str:
    name = path.stem
    doc_type = "spec" if path.parent.name == "specs" else "plan"
    status = doc_status(name, text)
    platform = platform_version(name)
    lines = [
        "---",
        f"doc_type: {doc_type}",
        f"status: {status}",
        f"platform_version: {platform}",
        "catalog: docs/superpowers/README.md",
        "---",
        "",
    ]
    return "\n".join(lines)


def inject_frontmatter(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if has_status_frontmatter(text):
        return False
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            block = text[3:end].strip()
            rest = text[end + 4 :].lstrip("\n")
            extra = build_frontmatter(path, rest).strip().strip("-").strip()
            # merge: prepend doc_type/status/platform to existing yaml block
            new_block = (
                "---\n"
                f"doc_type: {'spec' if path.parent.name == 'specs' else 'plan'}\n"
                f"status: {doc_status(path.stem, rest)}\n"
                f"platform_version: {platform_version(path.stem)}\n"
                f"catalog: docs/superpowers/README.md\n"
                f"{block}\n"
                "---\n\n"
            )
            path.write_text(new_block + rest, encoding="utf-8")
            return True
    fm = build_frontmatter(path, text)
    path.write_text(fm + text, encoding="utf-8")
    return True


def main() -> None:
    changed = 0
    for path in sorted(SP.rglob("*.md")):
        if path.name == "README.md":
            continue
        if inject_frontmatter(path):
            changed += 1
            print(f"tagged: {path.relative_to(ROOT)}")
    print(f"done: {changed} files updated")


if __name__ == "__main__":
    main()
