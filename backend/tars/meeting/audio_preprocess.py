"""Normalize meeting audio to 16 kHz mono WAV before ASR."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from typing import Any, Dict, List, Optional, Tuple


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def concat_webm_fragments(chunk_paths: List[str], output_path: Optional[str] = None) -> Tuple[str, List[str]]:
    """Binary-concatenate MediaRecorder webm fragments (valid for Chrome/Firefox timeslice)."""
    if not chunk_paths:
        raise ValueError("no audio chunks")
    cleanup: List[str] = []
    if output_path:
        out_path = output_path
    else:
        out = tempfile.NamedTemporaryFile(suffix=".webm", delete=False)
        out.close()
        out_path = out.name
        cleanup.append(out_path)
    with open(out_path, "wb") as outf:
        for path in chunk_paths:
            with open(path, "rb") as inf:
                outf.write(inf.read())
    return out_path, cleanup


def merge_audio_chunks(chunk_paths: List[str]) -> Tuple[str, List[str]]:
    """Merge browser-recorded chunks into one file for ASR."""
    if not chunk_paths:
        raise ValueError("no audio chunks")
    if len(chunk_paths) == 1:
        return chunk_paths[0], []

    first_ext = os.path.splitext(chunk_paths[0])[1].lower()
    if first_ext in (".webm", ".ogg", ".opus"):
        return concat_webm_fragments(chunk_paths)

    if not ffmpeg_available():
        return chunk_paths[-1], []

    out = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    out.close()
    cleanup: List[str] = [out.name]
    inputs: List[str] = []
    for path in chunk_paths:
        inputs.extend(["-i", path])
    n = len(chunk_paths)
    filter_str = "".join(f"[{i}:a]" for i in range(n)) + f"concat=n={n}:v=0:a=1[out]"
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        *inputs,
        "-filter_complex",
        filter_str,
        "-map",
        "[out]",
        "-ar",
        "16000",
        "-ac",
        "1",
        out.name,
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return out.name, cleanup
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        for path in cleanup:
            try:
                os.unlink(path)
            except OSError:
                pass
        err = e.stderr.decode("utf-8", errors="replace") if hasattr(e, "stderr") and e.stderr else str(e)
        print(f"[MeetingASR] ffmpeg 合并分片失败，尝试 webm 二进制拼接: {err[:200]}")
        return concat_webm_fragments(chunk_paths)


def preprocess_for_asr(
    input_path: str,
    cfg: Optional[Dict[str, Any]] = None,
) -> Tuple[str, List[str]]:
    """Return (path_for_asr, temp_files_to_cleanup).

    When preprocessing is disabled or ffmpeg is missing, returns the original path
    and an empty cleanup list.
    """
    from .config import load_meeting_asr_config

    cfg = cfg or load_meeting_asr_config()
    preprocess = cfg.get("preprocess") or {}
    if not preprocess.get("enabled", True):
        return input_path, []
    if not ffmpeg_available():
        print("[MeetingASR] ffmpeg 未安装，跳过音频预处理")
        return input_path, []

    sample_rate = int(preprocess.get("sample_rate", 16000))
    channels = int(preprocess.get("channels", 1))

    out = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    out.close()
    input_flags: List[str] = []
    if str(input_path).lower().endswith(".webm"):
        input_flags = ["-fflags", "+genpts+discardcorrupt", "-err_detect", "ignore_err"]

    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        *input_flags,
        "-i",
        input_path,
        "-ar",
        str(sample_rate),
        "-ac",
        str(channels),
        "-c:a",
        "pcm_s16le",
        out.name,
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return out.name, [out.name]
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        try:
            os.unlink(out.name)
        except OSError:
            pass
        err = e.stderr.decode("utf-8", errors="replace") if hasattr(e, "stderr") and e.stderr else str(e)
        print(f"[MeetingASR] ffmpeg 预处理失败，使用原文件: {err[:200]}")
        return input_path, []
