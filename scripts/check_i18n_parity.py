#!/usr/bin/env python3
"""i18n parity check — every key in zh must exist in en, and vice versa.

frontend/src/i18n/index.ts is structured as
    export const messages = { zh: { 'a.b': '...', ... }, en: { 'a.b': '...', ... } }
This script extracts the quoted dotted keys from each block and diffs them.

Usage:  python3 scripts/check_i18n_parity.py
exits 1 if divergence is found.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

I18N_FILE = Path(__file__).resolve().parents[1] / "frontend" / "src" / "i18n" / "index.ts"

_KEY_LINE = re.compile(r"^\s*'([A-Za-z0-9_.\-]+)'\s*:", re.MULTILINE)


def _slice_block(text: str, label: str) -> str:
    m = re.search(rf"\b{label}:\s*\{{", text)
    if not m:
        raise RuntimeError(f"could not find `{label}:` block in {I18N_FILE}")
    start = m.end() - 1
    depth = 0
    in_str: str | None = None
    escape = False
    for i, ch in enumerate(text[start:], start=start):
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == in_str:
                in_str = None
            continue
        if ch in ("'", '"', "`"):
            in_str = ch
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    raise RuntimeError(f"unbalanced braces while scanning `{label}:` block")


def _collect_keys(block: str) -> set[str]:
    return set(_KEY_LINE.findall(block))


def main() -> int:
    text = I18N_FILE.read_text(encoding="utf-8")
    zh = _collect_keys(_slice_block(text, "zh"))
    en = _collect_keys(_slice_block(text, "en"))

    missing_in_en = sorted(zh - en)
    missing_in_zh = sorted(en - zh)

    if not missing_in_en and not missing_in_zh:
        print(f"[i18n] OK — {len(zh)} keys, zh ⇄ en parity holds.")
        return 0

    if missing_in_en:
        print(f"[i18n] {len(missing_in_en)} keys missing in en:")
        for k in missing_in_en:
            print(f"  - {k}")
    if missing_in_zh:
        print(f"[i18n] {len(missing_in_zh)} keys missing in zh:")
        for k in missing_in_zh:
            print(f"  - {k}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
