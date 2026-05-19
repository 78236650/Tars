"""SkillHub 安装器 - 下载、校验、解压、注册、兼容性检查"""
import hashlib
import shutil
import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from .client import SkillHubClient
from .local_catalog import LocalSkillCatalog
from .models import SkillHubPackage


DANGEROUS_PERMISSIONS = {"command_exec", "file_write"}
TARS_VERSION = "2.7.0"  # 当前 TARS 版本


def _parse_version(v: str) -> tuple:
    """解析版本字符串为比较用的 tuple"""
    try:
        return tuple(int(x) for x in v.strip().split("."))
    except (ValueError, AttributeError):
        return (0, 0, 0)


class SkillInstaller:
    """管理 SkillHub 技能包的安装、卸载、更新"""

    def __init__(
        self,
        skills_dir: str,
        client: SkillHubClient,
        skill_loader=None,
        skill_registry=None,
        local_catalog: Optional[LocalSkillCatalog] = None,
    ):
        self.skills_dir = Path(skills_dir)
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.client = client
        self.skill_loader = skill_loader
        self.skill_registry = skill_registry
        self.local_catalog = local_catalog

    async def install(self, repo_full_name: str, confirm_permissions: bool = True) -> Dict[str, Any]:
        """安装流程：本地 bundled/package → 或 GitHub 远程下载"""
        if self.local_catalog:
            local_source = self.local_catalog.resolve_install_source(repo_full_name)
            if local_source:
                return self._install_local(local_source, confirm_permissions)

        pkg = await self.client.get_detail(repo_full_name)
        if not pkg:
            return {"success": False, "error": f"找不到仓库: {repo_full_name}"}

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            archive_path = tmp_path / "package.tar.gz"

            ok = await self.client.download(pkg, archive_path)
            if not ok:
                return {"success": False, "error": "下载失败"}

            # 校验 checksum（如果有）
            if pkg.checksum:
                actual = self._compute_sha256(archive_path)
                if actual != pkg.checksum:
                    return {"success": False, "error": "Checksum 校验失败，包可能被篡改"}

            # 解压到临时目录
            extract_dir = tmp_path / "extracted"
            extract_dir.mkdir()
            try:
                self._extract(archive_path, extract_dir)
            except Exception as e:
                return {"success": False, "error": f"解压失败: {e}"}

            skill_root = self._find_skill_root(extract_dir)
            if not skill_root:
                return {"success": False, "error": "包中未找到 skill.yaml 或 SKILL.md"}

            skill_id = self._detect_skill_id(skill_root) or pkg.name
            target_dir = self.skills_dir / skill_id
            if target_dir.exists():
                shutil.rmtree(target_dir)
            shutil.copytree(skill_root, target_dir)

            return self._finalize_install(target_dir, skill_id, confirm_permissions, entry=None)

    def _install_local(self, local_source: Dict[str, Any], confirm_permissions: bool) -> Dict[str, Any]:
        """从 bundled .md 或 package 目录安装"""
        entry = local_source.get("entry") or {}
        source_path: Path = local_source["path"]
        source_type = local_source["type"]

        if source_type == "bundled":
            meta = LocalSkillCatalog._parse_md_frontmatter(source_path)
            skill_id = (
                entry.get("install_id")
                or meta.get("slug")
                or meta.get("name")
                or source_path.stem
            )
            # 目录名安全化
            skill_id = str(skill_id).replace("/", "-").replace(" ", "-").lower()
            target_dir = self.skills_dir / skill_id
            if target_dir.exists():
                shutil.rmtree(target_dir)
            target_dir.mkdir(parents=True)
            shutil.copy2(source_path, target_dir / "SKILL.md")
            skill_root = target_dir
        else:
            skill_id = entry.get("package_dir") or source_path.name
            target_dir = self.skills_dir / skill_id
            if target_dir.exists():
                shutil.rmtree(target_dir)
            shutil.copytree(source_path, target_dir)
            skill_root = target_dir

        return self._finalize_install(skill_root, skill_id, confirm_permissions, entry=entry)

    def _finalize_install(
        self,
        skill_root: Path,
        fallback_id: str,
        confirm_permissions: bool,
        entry: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """复制完成后：兼容性检查 → 加载注册 → 自检"""
        yaml_path = skill_root / "skill.yaml"
        md_path = skill_root / "SKILL.md"

        if yaml_path.exists():
            compat_result = self._check_compatibility(yaml_path)
            if not compat_result["compatible"]:
                return {
                    "success": False,
                    "error": compat_result["error"],
                    "compatibility": compat_result,
                }
            permissions = self._read_permissions(yaml_path)
            skill_id = self._read_skill_id(yaml_path) or fallback_id
        elif md_path.exists():
            permissions = self._read_permissions_md(md_path)
            meta = LocalSkillCatalog._parse_md_frontmatter(md_path)
            raw_name = meta.get("slug") or meta.get("name") or fallback_id
            skill_id = str(raw_name).replace("/", "-").replace(" ", "-").lower()
        else:
            return {"success": False, "error": "包中未找到 skill.yaml 或 SKILL.md"}

        if confirm_permissions and self._has_dangerous_permissions(permissions):
            return {
                "success": False,
                "needs_confirmation": True,
                "permissions": permissions,
                "error": "需要权限确认",
            }

        skill = self._load_installed_skill(skill_root, yaml_path, md_path)
        if skill:
            skill.source = "skillhub"
            skill.enabled = True
            if self.skill_registry:
                self.skill_registry.register(skill)

        self._invalidate_loader_cache()
        verify_result = self._post_install_verify(skill_id, skill)

        usage = entry.get("usage") if entry else None
        example_prompt = entry.get("example_prompt") if entry else None
        if not usage:
            usage = self._get_usage_text(skill_id, skill, yaml_path if yaml_path.exists() else md_path)

        result = {
            "success": True,
            "skill_id": skill_id,
            "usage": usage,
            "example_prompt": example_prompt or "",
            "verified": verify_result["ok"],
            "ready": True,
        }
        if skill:
            result["skill"] = skill.to_dict()
        if not verify_result["ok"]:
            result["warning"] = verify_result["warning"]
        return result

    def _load_installed_skill(self, skill_root: Path, yaml_path: Path, md_path: Path):
        if not self.skill_loader:
            return None
        if md_path.exists():
            return self.skill_loader._load_skill_md(md_path, skill_root)
        if yaml_path.exists():
            return self.skill_loader._load_skill(yaml_path, skill_root)
        return None

    def _invalidate_loader_cache(self) -> None:
        if not self.skill_loader:
            return
        try:
            from ..skills.loader import MANIFEST_FILE
            MANIFEST_FILE.unlink(missing_ok=True)
        except Exception:
            pass
        if hasattr(self.skill_loader, "_disclosure_cache"):
            del self.skill_loader._disclosure_cache

    def uninstall(self, skill_id: str) -> Dict[str, Any]:
        target = self.skills_dir / skill_id
        if not target.exists():
            return {"success": False, "error": f"技能 {skill_id} 未安装"}
        try:
            # 从 skill_registry 注销
            if self.skill_registry:
                self.skill_registry.unregister(skill_id)
            shutil.rmtree(target)
            return {"success": True, "message": f"{skill_id} 已卸载"}
        except Exception as e:
            return {"success": False, "error": f"卸载失败: {e}"}

    async def update(self, skill_id: str) -> Dict[str, Any]:
        """通过重新安装实现更新"""
        return await self.install(skill_id, confirm_permissions=False)

    def list_installed(self) -> List[str]:
        if not self.skills_dir.exists():
            return []
        return [d.name for d in self.skills_dir.iterdir() if d.is_dir() and (d / "skill.yaml").exists()]

    async def check_updates(self, installed_ids: List[str]) -> List[Dict[str, str]]:
        """检查已安装技能的更新"""
        updates = []
        for sid in installed_ids:
            if "/" not in sid:
                continue  # 非 GitHub 来源，跳过
            pkg = await self.client.get_detail(sid)
            if pkg:
                updates.append({"id": sid, "latest_version": pkg.version})
        return updates

    # ========= 兼容性检查 =========

    def _check_compatibility(self, yaml_path: Path) -> Dict[str, Any]:
        """检查 skill.yaml 声明的兼容性"""
        try:
            import yaml
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception:
            return {"compatible": True}  # 解析失败不阻塞安装

        tars_min = data.get("tars_version_min")
        if tars_min:
            current = _parse_version(TARS_VERSION)
            required = _parse_version(tars_min)
            if current < required:
                return {
                    "compatible": False,
                    "error": f"此技能要求 TARS >= {tars_min}，当前版本为 {TARS_VERSION}",
                    "tars_version_min": tars_min,
                    "current_version": TARS_VERSION,
                }

        # 检查 Python 包依赖
        requires_packages = data.get("requires_packages", [])
        missing_packages = []
        for pkg_spec in requires_packages:
            pkg_name = pkg_spec.split(">=")[0].split("==")[0].split(">")[0].strip()
            try:
                __import__(pkg_name.replace("-", "_"))
            except ImportError:
                missing_packages.append(pkg_spec)

        if missing_packages:
            return {
                "compatible": False,
                "error": f"缺少 Python 依赖: {', '.join(missing_packages)}。请执行: pip install {' '.join(missing_packages)}",
                "missing_packages": missing_packages,
            }

        return {"compatible": True}

    def _post_install_verify(self, skill_id: str, skill) -> Dict[str, Any]:
        """安装后自检"""
        if not skill:
            return {"ok": True}

        # 对 PluginSkill 验证工具注册
        if skill.type.value == "plugin" and self.skill_registry and self.skill_loader:
            tool_registry = getattr(self.skill_loader, "tool_registry", None)
            if tool_registry and skill.entry_point:
                tool = tool_registry.get(skill_id)
                if not tool:
                    return {
                        "ok": False,
                        "warning": f"技能已安装但工具 '{skill_id}' 未在 ToolRegistry 中找到，可能注册失败",
                    }
        return {"ok": True}

    @staticmethod
    def _get_usage_text(skill_id: str, skill, yaml_path: Path) -> str:
        """生成用法说明文本"""
        # 优先使用 skill.yaml 中的 usage 字段
        if skill and skill.usage:
            return skill.usage

        # 根据技能类型生成默认说明
        if skill:
            if skill.type.value == "plugin":
                return f"此技能已注册为工具 '{skill_id}'。在对话中，TARS 可以自动调用此工具；你也可以直接说 '使用 {skill_id} 来...' 来触发。"
            else:
                return f"此技能为提示词模板，已自动注入到每次对话的 system prompt 中。你无需主动调用，TARS 会在每次回复时参考此技能的指引。"

        # 兜底：尝试从 yaml 读取
        try:
            import yaml
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            if data.get("usage"):
                return data["usage"]
        except Exception:
            pass

        return f"技能 '{skill_id}' 已安装成功。在对话中即可生效。"

    # ========= 辅助方法 =========

    @staticmethod
    def _compute_sha256(file_path: Path) -> str:
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _extract(archive: Path, target: Path) -> None:
        if archive.name.endswith(".tar.gz") or archive.name.endswith(".tgz"):
            with tarfile.open(archive, "r:gz") as tf:
                SkillInstaller._safe_extract(tf, target)
        elif archive.name.endswith(".zip"):
            with zipfile.ZipFile(archive, "r") as zf:
                zf.extractall(target)
        else:
            # 尝试 tar.gz 解压（GitHub tarball 没后缀）
            try:
                with tarfile.open(archive, "r:gz") as tf:
                    SkillInstaller._safe_extract(tf, target)
            except Exception:
                raise ValueError("不支持的包格式")

    @staticmethod
    def _safe_extract(tf: tarfile.TarFile, target: Path) -> None:
        """防止路径穿越攻击的安全解压"""
        target_resolved = target.resolve()
        for member in tf.getmembers():
            member_path = (target / member.name).resolve()
            if not str(member_path).startswith(str(target_resolved)):
                raise ValueError(f"检测到不安全的路径: {member.name}")
        tf.extractall(target)

    @staticmethod
    def _find_skill_root(extracted_dir: Path) -> Optional[Path]:
        """查找包含 skill.yaml 或 SKILL.md 的目录"""
        if (extracted_dir / "skill.yaml").exists() or (extracted_dir / "SKILL.md").exists():
            return extracted_dir
        for item in extracted_dir.iterdir():
            if item.is_dir() and ((item / "skill.yaml").exists() or (item / "SKILL.md").exists()):
                return item
        return None

    @staticmethod
    def _read_permissions_md(md_path: Path) -> List[str]:
        try:
            import yaml
            content = md_path.read_text(encoding="utf-8")
            import re
            m = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
            if not m:
                return []
            data = yaml.safe_load(m.group(1)) or {}
            return data.get("permissions", [])
        except Exception:
            return []

    @staticmethod
    def _detect_skill_id(skill_root: Path) -> Optional[str]:
        yaml_path = skill_root / "skill.yaml"
        md_path = skill_root / "SKILL.md"
        if yaml_path.exists():
            return SkillInstaller._read_skill_id(yaml_path)
        if md_path.exists():
            meta = LocalSkillCatalog._parse_md_frontmatter(md_path)
            return meta.get("name")
        return None

    @staticmethod
    def _read_permissions(yaml_path: Path) -> List[str]:
        try:
            import yaml
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            return data.get("permissions", [])
        except Exception:
            return []

    @staticmethod
    def _read_skill_id(yaml_path: Path) -> Optional[str]:
        try:
            import yaml
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            return data.get("id")
        except Exception:
            return None

    @staticmethod
    def _has_dangerous_permissions(permissions: List[str]) -> bool:
        return any(p in DANGEROUS_PERMISSIONS for p in permissions)
