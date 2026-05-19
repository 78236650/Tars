"""Skill package dependency checker — v4.1.0"""
import importlib.util
import json
import re
import shutil
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


@dataclass
class DependencyReport:
    ok: bool
    missing_bins: List[str] = field(default_factory=list)
    missing_packages: List[str] = field(default_factory=list)
    install_hints: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "missing_bins": self.missing_bins,
            "missing_packages": self.missing_packages,
            "install_hints": self.install_hints,
        }


class DependencyChecker:
    """Check CLI binaries and Python packages declared by a skill."""

    def check(self, meta: Dict[str, Any]) -> DependencyReport:
        requires = meta.get("requires") or {}
        bins = list(requires.get("bins") or [])
        packages = list(requires.get("packages") or meta.get("requires_packages") or [])

        # Agent Skills metadata.clawdbot.requires.bins
        md_meta = meta.get("metadata")
        if isinstance(md_meta, str):
            try:
                md_meta = json.loads(md_meta)
            except json.JSONDecodeError:
                md_meta = {}
        if isinstance(md_meta, dict):
            claw = md_meta.get("clawdbot") or md_meta.get("clawdbot", {})
            if isinstance(claw, dict):
                req = claw.get("requires") or {}
                for b in req.get("bins") or []:
                    if b not in bins:
                        bins.append(b)
                install_specs = claw.get("install") or []
                hints = self._hints_from_install_specs(install_specs)
            else:
                hints = list(meta.get("install_hints") or [])
        else:
            hints = list(meta.get("install_hints") or [])

        missing_bins = [b for b in bins if not shutil.which(b)]
        missing_packages = []
        for pkg_spec in packages:
            pkg_name = pkg_spec.split(">=")[0].split("==")[0].split(">")[0].strip()
            mod = pkg_name.replace("-", "_")
            if importlib.util.find_spec(mod) is None:
                missing_packages.append(pkg_spec)
                hints.append(f"pip install {pkg_spec}")

        for b in missing_bins:
            hints.append(f"安装 CLI 工具: {b}")

        ok = not missing_bins and not missing_packages
        return DependencyReport(
            ok=ok,
            missing_bins=missing_bins,
            missing_packages=missing_packages,
            install_hints=hints,
        )

    @staticmethod
    def _hints_from_install_specs(specs: List[Any]) -> List[str]:
        hints = []
        for spec in specs:
            if not isinstance(spec, dict):
                continue
            label = spec.get("label")
            if label:
                hints.append(label)
            elif spec.get("kind") == "brew" and spec.get("formula"):
                hints.append(f"brew install {spec['formula']}")
            elif spec.get("kind") == "pip" and spec.get("package"):
                hints.append(f"pip install {spec['package']}")
        return hints

    @staticmethod
    def parse_meta_from_md(content: str) -> Dict[str, Any]:
        m = FRONTMATTER_RE.match(content)
        if not m:
            return {}
        try:
            import yaml
            return yaml.safe_load(m.group(1)) or {}
        except Exception:
            return {}
