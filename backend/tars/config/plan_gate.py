"""Plan approval gate configuration — v4.3.2"""
import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

_CONFIG: Optional[Dict[str, Any]] = None


def _config_path() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "config" / "modules.yaml"


def load_plan_gate_config() -> Dict[str, Any]:
    global _CONFIG
    if _CONFIG is not None:
        return _CONFIG

    defaults = {
        "enabled": True,
        "always_approve": False,
        "force_auto_approve": False,
        "auto_approve_threshold": 3,
        "review_timeout_sec": 600,
        "reminder_at_sec": 300,
        "fallback_auto_approve": True,
    }

    path = _config_path()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
            merged = {**defaults, **(raw.get("plan_gate") or {})}
            _CONFIG = merged
            return _CONFIG
        except Exception as e:
            print(f"[PlanGateConfig] 加载失败，使用默认: {e}")

    env_enabled = os.getenv("TARS_PLAN_GATE", "")
    if env_enabled.lower() in ("0", "false", "no"):
        defaults["enabled"] = False

    _CONFIG = defaults
    return _CONFIG


class PlanGateConfig:
    def __init__(self, data: Optional[Dict[str, Any]] = None):
        cfg = data or load_plan_gate_config()
        self.enabled = bool(cfg.get("enabled", True))
        self.always_approve = bool(cfg.get("always_approve", False))
        self.force_auto_approve = bool(cfg.get("force_auto_approve", False))
        self.auto_approve_threshold = int(cfg.get("auto_approve_threshold", 3))
        self.review_timeout_sec = int(cfg.get("review_timeout_sec", 600))
        self.reminder_at_sec = int(cfg.get("reminder_at_sec", 300))
        self.fallback_auto_approve = bool(cfg.get("fallback_auto_approve", True))


plan_gate_config = PlanGateConfig()
