"""Process pool for CPU-bound ASR (Whisper / SenseVoice)."""
from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor
from typing import Optional

_pool: Optional[ProcessPoolExecutor] = None


def _init_asr_worker() -> None:
    """Allow HuggingFace downloads in ASR workers only (main process stays offline for embeddings)."""
    os.environ["HF_HUB_OFFLINE"] = "0"
    os.environ["TRANSFORMERS_OFFLINE"] = "0"


def get_asr_pool() -> ProcessPoolExecutor:
    global _pool
    if _pool is None:
        _pool = ProcessPoolExecutor(max_workers=2, initializer=_init_asr_worker)
    return _pool


def shutdown_asr_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.shutdown(wait=False)
        _pool = None


# Backward-compatible aliases
get_whisper_pool = get_asr_pool
shutdown_whisper_pool = shutdown_asr_pool
