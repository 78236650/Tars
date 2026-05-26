"""SKILL.md 解析器 — v2.5 Agent Skills 规范

读取 SKILL.md 的 YAML frontmatter + Markdown body
"""
import re
from pathlib import Path
from typing import Optional, Dict, Any
import yaml


FRONTMATTER_RE = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.DOTALL)


class SKILL:
    """Agent Skills 规范的 SKILL.md 解析结果"""

    def __init__(self, name: str = "", description: str = "",
                 body: str = "", dir_path: str = "",
                 permissions: list = None,
                 depends_on: list = None,
                 outputs: dict = None,
                 tars_version_min: str = "",
                 requires_packages: list = None,
                 triggers: list = None,
                 skip_when: list = None,
                 priority: int = 50,
                 verify: list = None,
                 verify_mode: str = "strict",
                 has_pdca: bool = False, has_scripts: bool = False):
        self.name = name
        self.description = description
        self.body = body                          # Markdown 正文
        self.dir_path = dir_path                  # 技能目录
        self.permissions = permissions or []
        self.depends_on = depends_on or []
        self.outputs = outputs or {}
        self.tars_version_min = tars_version_min
        self.requires_packages = requires_packages or []
        self.triggers = triggers or []
        self.skip_when = skip_when or []
        self.priority = priority
        self.verify = verify or []
        self.verify_mode = verify_mode or "strict"
        self.has_pdca = has_pdca
        self.has_scripts = has_scripts

    def to_dict(self) -> dict:
        return {
            "id": self.name, "name": self.name,
            "description": self.description,
            "dir_path": self.dir_path,
            "has_pdca": self.has_pdca,
            "has_scripts": self.has_scripts,
            "permissions": self.permissions,
            "depends_on": self.depends_on,
            "outputs": self.outputs,
            "tars_version_min": self.tars_version_min,
            "body": self.body,
        }

    @property
    def trigger_description(self) -> str:
        """用于渐进披露——注入 system prompt 的简短描述"""
        return f"- **{self.name}**: {self.description}"


def parse_skill_md(file_path: str) -> Optional[SKILL]:
    """解析一个 SKILL.md 文件"""
    path = Path(file_path)
    if not path.exists():
        return None

    content = path.read_text(encoding="utf-8")
    m = FRONTMATTER_RE.match(content)
    if not m:
        # 无 frontmatter——整个文件作为 body，name 用目录名
        body = content.strip()
        return SKILL(
            name=path.parent.name,
            description=body.split('\n')[0][:200] if body else "",
            body=body,
            dir_path=str(path.parent),
        )

    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        meta = {}

    body = content[m.end():].strip()
    dir_path = str(path.parent)
    name = meta.get("name", path.parent.name)

    has_pdca = (path.parent / "pdca.yaml").exists()
    has_scripts = (path.parent / "scripts").is_dir()

    return SKILL(
        name=name,
        description=meta.get("description", ""),
        body=body,
        dir_path=dir_path,
        permissions=meta.get("permissions", []),
        depends_on=meta.get("depends_on", []),
        outputs=meta.get("outputs", {}),
        tars_version_min=meta.get("tars_version_min", ""),
        requires_packages=meta.get("requires_packages", []),
        triggers=meta.get("triggers", []) or [],
        skip_when=meta.get("skip_when", []) or [],
        priority=int(meta.get("priority", 50)),
        verify=meta.get("verify", []) or [],
        verify_mode=str(meta.get("verify_mode", "strict")),
        has_pdca=has_pdca,
        has_scripts=has_scripts,
    )


def parse_skills_dir(skills_dir: str) -> list[SKILL]:
    """扫描目录下所有 SKILL.md"""
    skills = []
    base = Path(skills_dir)
    if not base.exists():
        return skills

    for skill_dir in sorted(base.iterdir()):
        if not skill_dir.is_dir() or skill_dir.name.startswith("."):
            continue
        md_path = skill_dir / "SKILL.md"
        if md_path.exists():
            skill = parse_skill_md(str(md_path))
            if skill:
                skills.append(skill)

    return skills
