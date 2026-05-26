"""Verification gate configuration — v4.3.2"""
import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

_CONFIG: Optional[Dict[str, Any]] = None


def _config_path() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "config" / "modules.yaml"


def load_verification_config() -> Dict[str, Any]:
    global _CONFIG
    if _CONFIG is not None:
        return _CONFIG

    defaults = {
        "enabled": True,
        "default_mode": "strict",
        "lenient_pass_rate": 0.8,
        "fail_action": "rollback",
    }

    path = _config_path()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
            merged = {**defaults, **(raw.get("verification") or {})}
            _CONFIG = merged
            return _CONFIG
        except Exception as e:
            print(f"[VerificationConfig] 加载失败，使用默认: {e}")

    if os.getenv("TARS_VERIFICATION", "").lower() in ("0", "false", "no"):
        defaults["enabled"] = False

    _CONFIG = defaults
    return _CONFIG


class VerificationConfig:
    def __init__(self, data: Optional[Dict[str, Any]] = None):
        cfg = data or load_verification_config()
        self.enabled = bool(cfg.get("enabled", True))
        self.default_mode = str(cfg.get("default_mode", "strict"))
        self.lenient_pass_rate = float(cfg.get("lenient_pass_rate", 0.8))
        self.fail_action = str(cfg.get("fail_action", "rollback"))


verification_config = VerificationConfig()
