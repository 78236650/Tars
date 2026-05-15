"""SkillHub 安装器 - 下载、校验、解压、注册、兼容性检查"""
import hashlib
import shutil
import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from .client import SkillHubClient
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

    def __init__(self, skills_dir: str, client: SkillHubClient, skill_loader=None, skill_registry=None):
        self.skills_dir = Path(skills_dir)
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.client = client
        self.skill_loader = skill_loader
        self.skill_registry = skill_registry

    async def install(self, repo_full_name: str, confirm_permissions: bool = True) -> Dict[str, Any]:
        """安装流程：获取详情 → 下载 → 校验 → 解压 → 兼容性检查 → 加载 → 自检"""
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

            # 找到 skill.yaml
            skill_root = self._find_skill_root(extract_dir)
            if not skill_root:
                return {"success": False, "error": "包中未找到 skill.yaml"}

            # 解析并兼容性检查
            yaml_path = skill_root / "skill.yaml"
            compat_result = self._check_compatibility(yaml_path)
            if not compat_result["compatible"]:
                return {
                    "success": False,
                    "error": compat_result["error"],
                    "compatibility": compat_result,
                }

            # 解析权限声明
            permissions = self._read_permissions(yaml_path)
            if confirm_permissions and self._has_dangerous_permissions(permissions):
                return {
                    "success": False,
                    "needs_confirmation": True,
                    "permissions": permissions,
                    "error": "需要权限确认",
                }

            # 复制到 skills 目录
            skill_id = self._read_skill_id(yaml_path) or pkg.name
            target_dir = self.skills_dir / skill_id
            if target_dir.exists():
                shutil.rmtree(target_dir)
            shutil.copytree(skill_root, target_dir)

            # 加载注册
            skill = None
            if self.skill_loader:
                skill = self.skill_loader._load_skill(target_dir / "skill.yaml", target_dir)
                if skill:
                    skill.source = "skillhub"

            # 安装后自检
            verify_result = self._post_install_verify(skill_id, skill)

            result = {
                "success": True,
                "skill_id": skill_id,
                "usage": self._get_usage_text(skill_id, skill, yaml_path),
                "verified": verify_result["ok"],
            }
            if skill:
                result["skill"] = skill.to_dict()
            if not verify_result["ok"]:
                result["warning"] = verify_result["warning"]
            return result

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
        """查找包含 skill.yaml 的目录"""
        if (extracted_dir / "skill.yaml").exists():
            return extracted_dir
        for item in extracted_dir.iterdir():
            if item.is_dir() and (item / "skill.yaml").exists():
                return item
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
