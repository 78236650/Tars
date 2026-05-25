"""ASR backend selection and unified sync entrypoint."""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from ..audio_preprocess import preprocess_for_asr
from ..config import load_meeting_asr_config


def _is_hf_offline() -> bool:
    return os.getenv("HF_HUB_OFFLINE", "0").strip().lower() in ("1", "true", "yes")


def _sensevoice_model_cached(cfg: Dict[str, Any]) -> bool:
    sv = cfg.get("sensevoice") or {}
    model_id = str(sv.get("model", "iic/SenseVoiceSmall"))

    ms_cache = os.getenv("MODELSCOPE_CACHE", os.path.expanduser("~/.cache/modelscope"))
    for rel in (f"hub/models/{model_id}", f"hub/{model_id}"):
        path = os.path.join(ms_cache, rel)
        if os.path.isdir(path) and os.listdir(path):
            return True

    if "/" in model_id:
        org, name = model_id.split("/", 1)
        hf_id = f"models--{org}--{name.replace('/', '--')}"
    else:
        hf_id = f"models--{model_id}"
    hf_home = os.getenv("HF_HOME", os.path.expanduser("~/.cache/huggingface"))
    snapshots = os.path.join(hf_home, "hub", hf_id, "snapshots")
    if os.path.isdir(snapshots) and os.listdir(snapshots):
        return True
    return False


def _should_fallback_to_whisper(error: str) -> bool:
    err = error.lower()
    return any(
        token in err
        for token in (
            "cached snapshot",
            "hf_hub_offline",
            "outgoing traffic has been disabled",
            "connection error",
            "modelscope",
        )
    )


def resolve_backend_name(cfg: Optional[Dict[str, Any]] = None) -> str:
    cfg = cfg or load_meeting_asr_config()
    backend = (os.getenv("TARS_MEETING_ASR_BACKEND") or cfg.get("backend") or "whisper").strip().lower()
    if backend != "sensevoice":
        return "whisper"
    try:
        import funasr  # noqa: F401
    except ImportError:
        print("[MeetingASR] sensevoice 未安装，回退 whisper")
        return "whisper"
    if _is_hf_offline() and not _sensevoice_model_cached(cfg):
        print("[MeetingASR] SenseVoice 模型未缓存且 HF 离线，回退 whisper")
        return "whisper"
    return "sensevoice"


def display_model_name(cfg: Optional[Dict[str, Any]] = None) -> str:
    cfg = cfg or load_meeting_asr_config()
    backend = resolve_backend_name(cfg)
    if backend == "sensevoice":
        sv = cfg.get("sensevoice") or {}
        mid = str(sv.get("model", "iic/SenseVoiceSmall"))
        return mid.split("/")[-1] if "/" in mid else mid
    return f"whisper-{cfg.get('model', 'small')}"


def sync_transcribe(
    file_path: str,
    language: Optional[str] = None,
    model_override: Optional[str] = None,
) -> dict:
    """Run ASR in worker process: preprocess → backend transcribe."""
    cfg = load_meeting_asr_config()
    asr_path, cleanup = preprocess_for_asr(file_path, cfg)
    try:
        backend = resolve_backend_name(cfg)
        whisper_model = model_override or cfg.get("model")
        if backend == "sensevoice":
            from .sensevoice_backend import transcribe as sv_transcribe
            from .whisper_backend import transcribe as whisper_transcribe

            result = sv_transcribe(asr_path, language, cfg)
            if result.get("success"):
                return result
            err = str(result.get("error", ""))
            if _should_fallback_to_whisper(err):
                print(f"[MeetingASR] SenseVoice 失败，回退 whisper: {err}")
                return whisper_transcribe(asr_path, language, whisper_model)
            return result
        from .whisper_backend import transcribe as whisper_transcribe

        return whisper_transcribe(asr_path, language, whisper_model)
    finally:
        for path in cleanup:
            if path != file_path:
                try:
                    os.unlink(path)
                except OSError:
                    pass


# Backward-compatible alias used by legacy imports
_sync_transcribe = sync_transcribe
