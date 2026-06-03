"""SenseVoice ASR backend — best local zh/en mixed accuracy (FunASR)."""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from ..config import load_meeting_asr_config
from ..transcript import normalize_transcript_text

_worker_models: Dict[str, Any] = {}


def _map_language(language: Optional[str]) -> str:
    if not language:
        return "auto"
    lang = str(language).strip().lower()
    if lang in ("zh", "zh-cn", "zh-hans", "mandarin", "cmn"):
        return "zh"
    if lang.startswith("en"):
        return "en"
    if lang in ("ja", "ko", "yue"):
        return lang
    return "auto"


def transcribe(
    file_path: str,
    language: Optional[str] = None,
    cfg: Optional[Dict[str, Any]] = None,
) -> dict:
    try:
        from funasr import AutoModel
        from funasr.utils.postprocess_utils import rich_transcription_postprocess
    except ImportError:
        return {
            "success": False,
            "error": (
                "未安装 funasr（SenseVoice 引擎）。"
                "请执行: pip install funasr modelscope，或在 meeting.yaml 设置 backend: whisper"
            ),
        }

    cfg = cfg or load_meeting_asr_config()
    sv_cfg = cfg.get("sensevoice") or {}
    model_id = sv_cfg.get("model", "iic/SenseVoiceSmall")
    use_itn = bool(sv_cfg.get("use_itn", True))
    device = sv_cfg.get("device") or cfg.get("device", "cpu")
    if device == "auto":
        device = "cuda:0"
        try:
            import torch

            if not torch.cuda.is_available():
                device = "cpu"
        except ImportError:
            device = "cpu"

    cache_key = f"{model_id}:{device}"
    model = _worker_models.get(cache_key)
    if model is None:
        print(f"[MeetingASR:sensevoice] 加载 {model_id} ({device})，首次会下载模型…")
        prev_hf = os.environ.get("HF_HUB_OFFLINE")
        prev_tf = os.environ.get("TRANSFORMERS_OFFLINE")
        os.environ["HF_HUB_OFFLINE"] = "0"
        os.environ["TRANSFORMERS_OFFLINE"] = "0"
        try:
            model = AutoModel(
                model=model_id,
                trust_remote_code=True,
                vad_model=sv_cfg.get("vad_model", "fsmn-vad"),
                vad_kwargs={"max_single_segment_time": int(sv_cfg.get("max_segment_ms", 30000))},
                device=device,
            )
            _worker_models[cache_key] = model
        finally:
            if prev_hf is None:
                os.environ.pop("HF_HUB_OFFLINE", None)
            else:
                os.environ["HF_HUB_OFFLINE"] = prev_hf
            if prev_tf is None:
                os.environ.pop("TRANSFORMERS_OFFLINE", None)
            else:
                os.environ["TRANSFORMERS_OFFLINE"] = prev_tf

    try:
        res = model.generate(
            input=file_path,
            cache={},
            language=_map_language(language),
            use_itn=use_itn,
            batch_size_s=int(sv_cfg.get("batch_size_s", 60)),
            merge_vad=bool(sv_cfg.get("merge_vad", True)),
            merge_length_s=int(sv_cfg.get("merge_length_s", 15)),
        )
        raw_text = res[0].get("text", "") if res else ""
        text = rich_transcription_postprocess(raw_text)
        to_simplified = str(cfg.get("output_script", "simplified")).lower() == "simplified"
        text = normalize_transcript_text(text.strip(), to_simplified=to_simplified)

        # Extract segments: try timestamp-based split first, then sentence-split
        segments = []
        raw_timestamps = res[0].get("timestamp") if res else None
        if raw_timestamps and isinstance(raw_timestamps, list):
            # timestamp = [[start_ms, end_ms], ...] per text token
            sentences = res[0].get("sentence_info", []) if res else []
            if sentences:
                for si in sentences:
                    seg_text = si.get("text", "").strip()
                    if seg_text:
                        seg_text = normalize_transcript_text(seg_text, to_simplified=to_simplified)
                        segments.append({
                            "start": si.get("start", 0) / 1000.0,
                            "end": si.get("end", 0) / 1000.0,
                            "text": seg_text,
                        })
        if not segments and text:
            # Fallback: sentence-level split (no timestamps, but better than one giant block)
            import re
            sentences_raw = re.split(r"[。！？\n;；]", text)
            for s in sentences_raw:
                s = s.strip()
                if s:
                    segments.append({"text": s})

        return {
            "success": True,
            "text": text,
            "language": _map_language(language) if language else "auto",
            "duration": None,
            "segments": segments if segments else ([{"text": text}] if text else []),
            "model": "sensevoice-small",
            "backend": "sensevoice",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
