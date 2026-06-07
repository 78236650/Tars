"""Whisper ASR backend (faster-whisper)."""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Dict, Iterator, Optional

from ..config import (
    load_meeting_asr_config,
    resolve_asr_language,
    resolve_whisper_device,
    resolve_whisper_model_load_target,
    resolve_whisper_model_path,
)
from ..transcript import (
    _HALLUCINATION_MARKERS,
    filter_whisper_hallucinations,
    normalize_transcript_text,
)

_worker_models: Dict[str, Any] = {}


def _model_cache_key(load_target: str, device: str, compute_type: str) -> str:
    return f"{load_target}:{device}:{compute_type}"


@contextmanager
def _allow_model_download() -> Iterator[None]:
    """Ensure faster-whisper / VAD can reach HuggingFace Hub when models are not cached."""
    prev_hf = os.environ.get("HF_HUB_OFFLINE")
    prev_tf = os.environ.get("TRANSFORMERS_OFFLINE")
    os.environ["HF_HUB_OFFLINE"] = "0"
    os.environ["TRANSFORMERS_OFFLINE"] = "0"
    try:
        yield
    finally:
        if prev_hf is None:
            os.environ.pop("HF_HUB_OFFLINE", None)
        else:
            os.environ["HF_HUB_OFFLINE"] = prev_hf
        if prev_tf is None:
            os.environ.pop("TRANSFORMERS_OFFLINE", None)
        else:
            os.environ["TRANSFORMERS_OFFLINE"] = prev_tf


def _format_load_error(error: Exception) -> str:
    msg = str(error)
    lower = msg.lower()
    if "cached snapshot" in lower or "hf_hub_offline" in lower or "outgoing traffic" in lower:
        return (
            f"{msg}。"
            "Whisper 模型尚未缓存到本地，请确保 ASR worker 可联网完成首次下载，"
            "或预先下载 faster-whisper 对应模型。"
        )
    return msg


def transcribe(
    file_path: str,
    language: Optional[str] = None,
    model_size: Optional[str] = None,
) -> dict:
    try:
        from faster_whisper import WhisperModel

        cfg = load_meeting_asr_config()
        model_label = model_size or cfg.get("model", "small")
        load_target = resolve_whisper_model_load_target(cfg)
        local_path = resolve_whisper_model_path(cfg)
        device, compute_type = resolve_whisper_device(cfg)
        cache_key = _model_cache_key(load_target, device, compute_type)

        model = _worker_models.get(cache_key)
        if model is None:
            source = local_path or load_target
            print(f"[MeetingASR:whisper] 加载 {source} ({device}/{compute_type})…")
            if local_path:
                model = WhisperModel(local_path, device=device, compute_type=compute_type)
            else:
                with _allow_model_download():
                    model = WhisperModel(load_target, device=device, compute_type=compute_type)
            _worker_models[cache_key] = model

        resolved_language = resolve_asr_language(language)
        transcribe_kwargs: Dict[str, Any] = {
            "beam_size": int(cfg.get("beam_size", 5)),
            "vad_filter": bool(cfg.get("vad_filter", True)),
            "temperature": float(cfg.get("temperature", 0.0)),
            "condition_on_previous_text": False,
            "compression_ratio_threshold": 2.4,
            "log_prob_threshold": -1.0,
            "no_speech_threshold": 0.6,
        }
        if resolved_language:
            transcribe_kwargs["language"] = resolved_language
        prompt = (cfg.get("initial_prompt") or "").strip()
        # initial_prompt 仅作口语样例前缀，勿写「请使用…」类指令（易幻觉复读）
        if (
            prompt
            and resolved_language in (None, "zh")
            and not any(marker in prompt for marker in _HALLUCINATION_MARKERS)
        ):
            transcribe_kwargs["initial_prompt"] = prompt

        segments, info = model.transcribe(file_path, **transcribe_kwargs)

        segment_list = []
        texts = []
        for seg in segments:
            seg_text = (seg.text or "").strip()
            if not seg_text:
                continue
            texts.append(seg_text)
            segment_list.append({"start": seg.start, "end": seg.end, "text": seg_text})

        # 智能拼接：连续段落不强制换行，段落间加空格
        raw_joined = "".join(
            (t if (t.endswith("。") or t.endswith("！") or t.endswith("？") or t.endswith(".") or t.endswith("!") or t.endswith("?"))
             else t + " ")
            for t in texts
        ).strip()
        cleaned = filter_whisper_hallucinations(raw_joined, initial_prompt=prompt)
        to_simplified = str(cfg.get("output_script", "simplified")).lower() == "simplified"
        full_text = normalize_transcript_text(cleaned, to_simplified=to_simplified)
        if to_simplified:
            segment_list = [
                {**seg, "text": normalize_transcript_text(seg["text"], to_simplified=True)}
                for seg in segment_list
            ]

        return {
            "success": True,
            "text": full_text,
            "language": info.language,
            "duration": info.duration,
            "segments": segment_list,
            "model": f"whisper-{model_label}",
            "backend": "whisper",
        }
    except ImportError:
        return {
            "success": False,
            "error": "未安装 faster-whisper，请执行: pip install faster-whisper",
        }
    except Exception as e:
        return {"success": False, "error": _format_load_error(e)}
