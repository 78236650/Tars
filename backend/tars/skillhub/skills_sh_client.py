"""Skills.sh ecosystem client — v4.1.0"""
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import SkillHubPackage


class SkillsShClient:
    """Search skills.sh index with file cache + optional CLI refresh."""

    def __init__(
        self,
        cache_path: str,
        cache_ttl: int = 86400,
        enabled: bool = True,
    ):
        self.cache_path = Path(cache_path)
        self.cache_ttl = cache_ttl
        self.enabled = enabled

    async def search(self, query: str = "", limit: int = 20) -> List[SkillHubPackage]:
        if not self.enabled:
            return []

        entries = self._load_cache()
        if not entries or self._cache_expired():
            entries = await self._refresh_index()
            if entries:
                self._save_cache(entries)

        if query:
            q = query.lower()
            entries = [
                e for e in entries
                if q in e.get("name", "").lower()
                or q in e.get("description", "").lower()
                or q in " ".join(e.get("tags", [])).lower()
                or q in e.get("id", "").lower()
            ]

        return [self._entry_to_package(e) for e in entries[:limit]]

    async def _refresh_index(self) -> List[Dict[str, Any]]:
        """Try CLI, fallback to bundled seed index."""
        cli_results = await self._fetch_via_cli()
        if cli_results:
            return cli_results
        seed = self.cache_path.parent / "skills_sh_seed.json"
        if seed.exists():
            try:
                with open(seed, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    async def _fetch_via_cli(self) -> List[Dict[str, Any]]:
        import asyncio

        try:
            proc = await asyncio.create_subprocess_exec(
                "npx", "--yes", "skills", "find", "--json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=20.0)
            if proc.returncode != 0 or not stdout:
                return []
            return self._parse_cli_output(stdout.decode("utf-8", errors="replace"))
        except Exception as e:
            print(f"[SkillsSh] CLI 不可用: {e}")
            return []

    @staticmethod
    def _parse_cli_output(raw: str) -> List[Dict[str, Any]]:
        raw = raw.strip()
        if not raw:
            return []

        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return [SkillsShClient._normalize_entry(item) for item in data]
            if isinstance(data, dict) and "results" in data:
                return [SkillsShClient._normalize_entry(item) for item in data["results"]]
        except json.JSONDecodeError:
            pass

        entries = []
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = re.match(r"^(\S+)\s+[-–—]\s+(.+)$", line)
            if m:
                ref, desc = m.group(1), m.group(2)
                repo = SkillsShClient.resolve_repo(ref)
                entries.append({
                    "id": f"skills_sh/{repo.replace('/', '-')}",
                    "name": ref.split("/")[-1] if "/" in ref else ref,
                    "description": desc,
                    "author": repo.split("/")[0] if "/" in repo else "community",
                    "version": "latest",
                    "type": "prompt",
                    "tags": ["skills.sh"],
                    "source": "skills_sh",
                    "github_repo": repo,
                })
        return entries

    @staticmethod
    def _normalize_entry(item: Dict[str, Any]) -> Dict[str, Any]:
        ref = item.get("repo") or item.get("package") or item.get("name") or item.get("id", "")
        repo = SkillsShClient.resolve_repo(str(ref))
        return {
            "id": f"skills_sh/{repo}",
            "name": item.get("name") or repo.split("/")[-1],
            "description": item.get("description", ""),
            "author": item.get("author") or (repo.split("/")[0] if "/" in repo else "community"),
            "version": item.get("version", "latest"),
            "type": item.get("type", "prompt"),
            "tags": item.get("tags", ["skills.sh"]),
            "source": "skills_sh",
            "github_repo": repo,
            "stars": item.get("stars", 0),
        }

    @staticmethod
    def resolve_repo(package_ref: str) -> str:
        ref = package_ref.strip()
        if ref.startswith("skills_sh/"):
            ref = ref.replace("skills_sh/", "").replace("-", "/")
        if ref.count("/") == 1:
            return ref
        return ref

    def _load_cache(self) -> List[Dict[str, Any]]:
        if not self.cache_path.exists():
            return []
        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("entries", [])
        except Exception:
            return []

    def _cache_expired(self) -> bool:
        if not self.cache_path.exists():
            return True
        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            saved_at = data.get("saved_at", 0)
            return (time.time() - saved_at) > self.cache_ttl
        except Exception:
            return True

    def _save_cache(self, entries: List[Dict[str, Any]]) -> None:
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump({"saved_at": time.time(), "entries": entries}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[SkillsSh] 缓存写入失败: {e}")

    @staticmethod
    def _entry_to_package(entry: Dict[str, Any]) -> SkillHubPackage:
        repo = entry.get("github_repo", "")
        return SkillHubPackage(
            id=entry.get("id", repo),
            name=entry.get("name", ""),
            description=entry.get("description", ""),
            author=entry.get("author", ""),
            version=entry.get("version", "latest"),
            type=entry.get("type", "prompt"),
            tags=entry.get("tags", []),
            github_url=f"https://github.com/{repo}" if repo and "/" in repo else "",
            stars=entry.get("stars", 0),
        )
