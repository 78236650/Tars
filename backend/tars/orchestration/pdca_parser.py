"""pdca.yaml 解析器 — v2.5 确定性执行步骤定义

格式参考 docs/superpowers/specs/2026-05-09-skills-pdca-workspace-fusion-v1.1.md §5
"""
import yaml
from pathlib import Path
from typing import Optional, Dict, Any


class PDCAStep:
    def __init__(self, id: int, description: str, tool: str,
                 arguments: dict = None, verify: dict = None,
                 expected_artifacts: list = None):
        self.id = id
        self.description = description
        self.tool = tool
        self.arguments = arguments or {}
        self.verify = verify or {}
        self.expected_artifacts = expected_artifacts or []

    def to_dict(self) -> dict:
        return {
            "id": self.id, "description": self.description,
            "tool": self.tool, "arguments": self.arguments,
            "verify": self.verify,
            "expected_artifacts": self.expected_artifacts,
        }


class PDCAConfig:
    def __init__(self, steps: list = None, act: dict = None,
                 workspace: dict = None, plan_hint: str = ""):
        self.steps = steps or []
        self.act = act or {"max_retries": 3, "retry_backoff_s": [1, 2, 4], "on_final_failure": "ask_user"}
        self.workspace = workspace or {"mode": "resolve", "require_git": False}
        self.plan_hint = plan_hint


def parse_pdca_yaml(file_path: str) -> Optional[PDCAConfig]:
    """解析 pdca.yaml 文件"""
    path = Path(file_path)
    if not path.exists():
        return None

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    steps = []
    for s in data.get("steps", []):
        steps.append(PDCAStep(
            id=s.get("id", 0),
            description=s.get("description", ""),
            tool=s.get("tool", ""),
            arguments=s.get("arguments", {}),
            verify=s.get("verify", {}),
            expected_artifacts=s.get("expected_artifacts", []),
        ))

    return PDCAConfig(
        steps=steps,
        act=data.get("act", {}),
        workspace=data.get("workspace", {}),
        plan_hint=data.get("plan", {}).get("hint", ""),
    )


def parse_pdca_ref(pdca_ref: str, skills_dir: str = "skills") -> Optional[PDCAConfig]:
    """解析 skill://xxx/pdca.yaml 引用"""
    if not pdca_ref.startswith("skill://"):
        return None

    # skill://deploy/pdca.yaml → skills/deploy/pdca.yaml
    parts = pdca_ref.replace("skill://", "").split("/")
    skill_id = parts[0]
    filename = parts[1] if len(parts) > 1 else "pdca.yaml"

    yaml_path = Path(skills_dir) / skill_id / filename
    return parse_pdca_yaml(str(yaml_path))
