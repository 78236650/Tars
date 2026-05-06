"""SkillHub 客户端 - 基于 GitHub API"""
from typing import List, Optional

import httpx

from .models import SkillHubPackage


class SkillHubClient:
    """从 GitHub 搜索和获取 Skill 包"""

    def __init__(self, topic: str = "tars-skill", token: Optional[str] = None):
        self.topic = topic
        self.token = token
        self.api_base = "https://api.github.com"

    def _headers(self) -> dict:
        h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    async def search(self, query: str = "") -> List[SkillHubPackage]:
        """通过 GitHub topic 搜索 Skill 仓库"""
        q = f"topic:{self.topic}"
        if query:
            q += f" {query}"

        packages = []
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(
                    f"{self.api_base}/search/repositories",
                    headers=self._headers(),
                    params={"q": q, "sort": "stars", "order": "desc", "per_page": 30},
                )
                if resp.status_code != 200:
                    return []

                data = resp.json()
                for item in data.get("items", []):
                    pkg = await self._repo_to_package(client, item)
                    if pkg:
                        packages.append(pkg)
            except Exception as e:
                print(f"[SkillHub] 搜索失败: {e}")

        return packages

    async def get_detail(self, repo_full_name: str) -> Optional[SkillHubPackage]:
        """获取 owner/repo 格式仓库的详细信息"""
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(f"{self.api_base}/repos/{repo_full_name}", headers=self._headers())
                if resp.status_code != 200:
                    return None
                return await self._repo_to_package(client, resp.json())
            except Exception:
                return None

    async def _repo_to_package(self, client: httpx.AsyncClient, repo: dict) -> Optional[SkillHubPackage]:
        """将 GitHub 仓库信息转为 SkillHubPackage"""
        full_name = repo.get("full_name", "")
        if not full_name:
            return None

        # 获取最新 Release
        version = "latest"
        download_url = ""
        try:
            rel_resp = await client.get(f"{self.api_base}/repos/{full_name}/releases/latest", headers=self._headers())
            if rel_resp.status_code == 200:
                rel_data = rel_resp.json()
                version = rel_data.get("tag_name", "latest")
                for asset in rel_data.get("assets", []):
                    name = asset.get("name", "")
                    if name.endswith(".tar.gz") or name.endswith(".zip"):
                        download_url = asset.get("browser_download_url", "")
                        break
                if not download_url:
                    download_url = rel_data.get("tarball_url", "")
        except Exception:
            pass

        if not download_url:
            # 无 Release 时用默认分支的 tarball
            default_branch = repo.get("default_branch", "main")
            download_url = f"https://github.com/{full_name}/archive/refs/heads/{default_branch}.tar.gz"

        return SkillHubPackage(
            id=full_name,
            name=repo.get("name", ""),
            description=repo.get("description", "") or "",
            author=repo.get("owner", {}).get("login", ""),
            version=version,
            type="plugin",  # 默认，实际类型需解析 skill.yaml
            tags=repo.get("topics", []),
            github_url=repo.get("html_url", ""),
            download_url=download_url,
            stars=repo.get("stargazers_count", 0),
        )

    async def download(self, pkg: SkillHubPackage, target_path) -> bool:
        """下载包到指定路径"""
        if not pkg.download_url:
            return False

        try:
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                resp = await client.get(pkg.download_url, headers=self._headers())
                if resp.status_code != 200:
                    return False

                with open(target_path, "wb") as f:
                    f.write(resp.content)
            return True
        except Exception as e:
            print(f"[SkillHub] 下载失败: {e}")
            return False
