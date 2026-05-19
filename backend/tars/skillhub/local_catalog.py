"""SkillHub 本地技能目录 — 内置可安装技能包"""
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import SkillHubPackage

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


class LocalSkillCatalog:
    """管理 bundled 技能与 catalog.json 中的本地条目"""

    def __init__(
        self,
        catalog_path: Optional[str] = None,
        bundle_dir: Optional[str] = None,
        package_dir: Optional[str] = None,
    ):
        self.catalog_path = Path(catalog_path) if catalog_path else None
        self.bundle_dir = Path(bundle_dir) if bundle_dir else None
        self.package_dir = Path(package_dir) if package_dir else None

    def load_entries(self) -> List[Dict[str, Any]]:
        """加载 catalog.json，并自动补充 bundle 目录中未收录的 .md 技能"""
        entries: List[Dict[str, Any]] = []
        seen_ids: set[str] = set()

        if self.catalog_path and self.catalog_path.exists():
            try:
                with open(self.catalog_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                if isinstance(raw, list):
                    entries.extend(raw)
                    seen_ids.update(e.get("id", "") for e in raw)
            except Exception as e:
                print(f"[SkillHub] 读取 catalog 失败: {e}")

        if self.bundle_dir and self.bundle_dir.exists():
            for md_path in sorted(self.bundle_dir.glob("*.md")):
                skill_id = f"bundled/{md_path.stem}"
                if skill_id in seen_ids:
                    continue
                meta = self._parse_md_frontmatter(md_path)
                entries.append({
                    "id": skill_id,
                    "name": meta.get("name") or md_path.stem,
                    "description": meta.get("description", ""),
                    "author": meta.get("author", "Agent Skills"),
                    "version": meta.get("version", "1.0.0"),
                    "type": "plugin" if (self.bundle_dir / md_path.stem / "main.py").exists() else "prompt",
                    "tags": meta.get("tags", []),
                    "source": "bundled",
                    "bundle_file": md_path.name,
                    "permissions": meta.get("permissions", []),
                    "usage": meta.get("usage", ""),
                    "example_prompt": meta.get("example_prompt", ""),
                    "featured": False,
                })
                seen_ids.add(skill_id)

        return entries

    def search(self, query: str = "") -> List[SkillHubPackage]:
        entries = self.load_entries()
        if query:
            q = query.lower()
            entries = [
                e for e in entries
                if q in e.get("name", "").lower()
                or q in e.get("description", "").lower()
                or q in " ".join(e.get("tags", [])).lower()
                or q in e.get("id", "").lower()
            ]
        return [self._entry_to_package(e) for e in entries]

    def get_entry(self, skill_id: str) -> Optional[Dict[str, Any]]:
        for entry in self.load_entries():
            if entry.get("id") == skill_id:
                return entry
        stem = skill_id.split("/")[-1] if "/" in skill_id else skill_id
        for entry in self.load_entries():
            if entry.get("id", "").endswith(f"/{stem}") or entry.get("name", "").lower() == stem.lower():
                return entry
        return None

    def resolve_install_source(self, skill_id: str) -> Optional[Dict[str, Any]]:
        """解析安装来源：bundled / package / github"""
        entry = self.get_entry(skill_id)
        if not entry:
            if skill_id.startswith("bundled/"):
                entry = {"id": skill_id, "source": "bundled", "bundle_file": f"{skill_id.split('/')[-1]}.md"}
            else:
                return None

        source = entry.get("source", "bundled")
        if source == "bundled":
            bundle_file = entry.get("bundle_file") or f"{skill_id.split('/')[-1]}.md"
            bundle_path = (self.bundle_dir / bundle_file) if self.bundle_dir else None
            if bundle_path and bundle_path.exists():
                return {"type": "bundled", "path": bundle_path, "entry": entry}
            return None

        if source == "package":
            pkg_name = entry.get("package_dir") or skill_id.split("/")[-1]
            pkg_path = (self.package_dir / pkg_name) if self.package_dir else None
            if pkg_path and pkg_path.is_dir():
                return {"type": "package", "path": pkg_path, "entry": entry}
            return None

        return None

    def _entry_to_package(self, entry: Dict[str, Any]) -> SkillHubPackage:
        return SkillHubPackage(
            id=entry.get("id", ""),
            name=entry.get("name", ""),
            description=entry.get("description", ""),
            author=entry.get("author", "TARS"),
            version=entry.get("version", "1.0.0"),
            type=entry.get("type", "prompt"),
            tags=entry.get("tags", []),
            permissions=entry.get("permissions", []),
            github_url=entry.get("github_url", ""),
            download_url=entry.get("download_url", ""),
            stars=entry.get("stars", 0),
        )

    @staticmethod
    def _parse_md_frontmatter(md_path: Path) -> Dict[str, Any]:
        try:
            import yaml
            content = md_path.read_text(encoding="utf-8")
            m = FRONTMATTER_RE.match(content)
            if not m:
                return {"name": md_path.stem}
            return yaml.safe_load(m.group(1)) or {}
        except Exception:
            return {"name": md_path.stem}
