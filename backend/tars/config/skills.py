"""Skills system configuration — v4.1.0"""
import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

_CONFIG: Optional[Dict[str, Any]] = None


def _config_path() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "config" / "skills.yaml"


def _expand_env(value: Any) -> Any:
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        key = value[2:-1]
        return os.getenv(key, "")
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    return value


def load_skills_config() -> Dict[str, Any]:
    global _CONFIG
    if _CONFIG is not None:
        return _CONFIG

    defaults = {
        "skillhub": {
            "skills_sh_enabled": True,
            "skills_sh_cache_ttl": 86400,
            "github_topic": "tars-skill",
        },
        "router": {
            "enabled": True,
            "top_k": 3,
            "min_score": 0.25,
            "auto_archive_days": 30,
            "use_embedding": True,
            "embedding_model": "BAAI/bge-small-zh-v1.5",
            "cache_ttl_sec": 300,
        },
        "install": {
            "confirm_dangerous_permissions": True,
            "default_scope": "tenant",
        },
    }

    path = _config_path()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
            merged = {**defaults, **_expand_env(raw)}
            for section in ("skillhub", "router", "install"):
                if section in raw:
                    merged[section] = {**defaults.get(section, {}), **_expand_env(raw[section])}
            _CONFIG = merged
            return _CONFIG
        except Exception as e:
            print(f"[SkillsConfig] 加载失败，使用默认: {e}")

    _CONFIG = defaults
    return _CONFIG


class SkillsConfig:
    """技能系统运行时配置"""

    def __init__(self, data: Optional[Dict[str, Any]] = None):
        cfg = data or load_skills_config()
        sh = cfg.get("skillhub", {})
        rt = cfg.get("router", {})
        inst = cfg.get("install", {})

        self.skills_sh_enabled = bool(sh.get("skills_sh_enabled", True))
        self.skills_sh_cache_ttl = int(sh.get("skills_sh_cache_ttl", 86400))
        self.github_topic = sh.get("github_topic", "tars-skill")

        self.router_enabled = bool(rt.get("enabled", True))
        self.skill_top_k = int(rt.get("top_k", 3))
        self.skill_min_score = float(rt.get("min_score", 0.25))
        self.auto_archive_days = int(rt.get("auto_archive_days", 30))
        self.use_embedding = bool(rt.get("use_embedding", True))
        self.embedding_model = str(rt.get("embedding_model", "BAAI/bge-small-zh-v1.5"))
        self.cache_ttl_sec = int(rt.get("cache_ttl_sec", 300))

        self.confirm_dangerous_permissions = bool(inst.get("confirm_dangerous_permissions", True))
        self.default_install_scope = str(inst.get("default_scope", "tenant"))


skills_config = SkillsConfig()
