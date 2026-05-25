"""加载 meeting.yaml ASR 配置，支持环境变量覆盖。"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Dict, Optional

import yaml

WHISPER_MODEL_OPTIONS: tuple[str, ...] = (
    "tiny",
    "base",
    "small",
    "medium",
    "large-v2",
    "large-v3",
)

_runtime_asr_overrides: Dict[str, Any] = {}


def set_meeting_asr_runtime(overrides: Optional[Dict[str, Any]] = None) -> None:
    """Apply in-memory ASR overrides (UI settings until process restart)."""
    _runtime_asr_overrides.clear()
    if overrides:
        _runtime_asr_overrides.update(overrides)


def get_whisper_model_options() -> list[dict[str, str]]:
    labels = {
        "tiny": "最快，适合快速预览",
        "base": "较快，准确度一般",
        "small": "速度与准确度平衡（推荐）",
        "medium": "更准确，速度较慢",
        "large-v2": "高准确度，资源占用大",
        "large-v3": "最高准确度，需较大内存",
    }
    return [{"id": mid, "label": labels.get(mid, mid)} for mid in WHISPER_MODEL_OPTIONS]


_DEFAULT_ASR: Dict[str, Any] = {
    "backend": "sensevoice",
    "model": "small",
    "device": "auto",
    "compute_type": "auto",
    "language_default": "zh",
    "output_script": "simplified",
    "initial_prompt": "",
    "beam_size": 5,
    "vad_filter": True,
    "temperature": 0.0,
    "preprocess": {"enabled": True, "sample_rate": 16000, "channels": 1},
    "sensevoice": {
        "model": "iic/SenseVoiceSmall",
        "use_itn": True,
        "vad_model": "fsmn-vad",
        "max_segment_ms": 30000,
        "batch_size_s": 60,
        "merge_vad": True,
        "merge_length_s": 15,
        "device": "auto",
    },
    "realtime": {"mode": "hybrid", "partial_interval_sec": 12, "min_audio_chunks_for_partial": 2},
}


def _config_path() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "config",
        "meeting.yaml",
    )


def _deep_merge(base: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for key, val in incoming.items():
        if key in out and isinstance(out[key], dict) and isinstance(val, dict):
            out[key] = _deep_merge(out[key], val)
        else:
            out[key] = val
    return out


@lru_cache(maxsize=1)
def _load_meeting_asr_config_base() -> Dict[str, Any]:
    cfg = dict(_DEFAULT_ASR)
    path = _config_path()
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
            incoming = (raw.get("meeting") or {}).get("asr") or raw.get("asr") or {}
            if isinstance(incoming, dict):
                cfg = _deep_merge(cfg, incoming)
        except Exception as e:
            print(f"[MeetingConfig] load failed: {e}")

    env_model = os.getenv("TARS_MEETING_ASR_MODEL")
    if env_model:
        cfg["model"] = env_model.strip()
    env_lang = os.getenv("TARS_MEETING_ASR_LANGUAGE")
    if env_lang:
        cfg["language_default"] = env_lang.strip().lower()
    env_device = os.getenv("TARS_MEETING_ASR_DEVICE")
    if env_device:
        cfg["device"] = env_device.strip().lower()
    env_backend = os.getenv("TARS_MEETING_ASR_BACKEND")
    if env_backend:
        cfg["backend"] = env_backend.strip().lower()
    return cfg


def load_meeting_asr_config() -> Dict[str, Any]:
    cfg = dict(_load_meeting_asr_config_base())
    if _runtime_asr_overrides:
        cfg = _deep_merge(cfg, _runtime_asr_overrides)
    return cfg


def normalize_whisper_model(model: str) -> str:
    value = str(model or "").strip().lower()
    if value not in WHISPER_MODEL_OPTIONS:
        raise ValueError(f"unsupported whisper model: {model}")
    return value


def resolve_asr_language(user_language: Optional[str] = None) -> Optional[str]:
    """Map UI/API language hint to ASR language code (None = auto)."""
    if user_language is not None:
        hint = str(user_language).strip().lower()
        if hint in ("", "auto", "null", "none"):
            return None
        if hint in ("zh", "zh-cn", "zh-hans", "mandarin", "cmn", "普通话"):
            return "zh"
        if hint.startswith("en"):
            return "en"
        return hint

    default = str(load_meeting_asr_config().get("language_default", "zh")).lower()
    if default in ("", "auto"):
        return None
    if default in ("zh", "zh-cn", "zh-hans", "mandarin"):
        return "zh"
    if default.startswith("en"):
        return "en"
    return default


def _backend_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


def resolve_whisper_model_path(cfg: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Return absolute path to a local faster-whisper model dir (with model.bin), if available."""
    cfg = cfg or load_meeting_asr_config()
    candidates: list[str] = []
    raw = (cfg.get("model_path") or os.getenv("TARS_MEETING_WHISPER_MODEL_PATH") or "").strip()
    if raw:
        candidates.append(raw if os.path.isabs(raw) else os.path.join(_backend_root(), raw))
    model_size = str(cfg.get("model", "small"))
    candidates.append(os.path.join(_backend_root(), "data", "models", f"whisper-{model_size}"))
    candidates.append(os.path.join(_backend_root(), "data", "models", "whisper-small"))

    seen: set[str] = set()
    for path in candidates:
        if not path or path in seen:
            continue
        seen.add(path)
        if os.path.isfile(os.path.join(path, "model.bin")):
            return path
    return None


def resolve_whisper_model_load_target(cfg: Optional[Dict[str, Any]] = None) -> str:
    """Path or hub size id passed to faster_whisper.WhisperModel."""
    local = resolve_whisper_model_path(cfg)
    if local:
        return local
    return str((cfg or load_meeting_asr_config()).get("model", "small"))


def resolve_whisper_device(cfg: Optional[Dict[str, Any]] = None) -> tuple[str, str]:
    cfg = cfg or load_meeting_asr_config()
    device = str(cfg.get("device", "auto")).lower()
    compute = str(cfg.get("compute_type", "auto")).lower()

    if device == "auto":
        try:
            import ctranslate2

            device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
        except Exception:
            device = "cpu"

    if compute == "auto":
        compute = "float16" if device == "cuda" else "int8"
    return device, compute
