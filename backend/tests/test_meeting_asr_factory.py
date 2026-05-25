"""ASR backend factory tests."""
import os

import pytest

from tars.meeting.asr.factory import display_model_name, resolve_backend_name, sync_transcribe
from tars.meeting.asr.pool import _init_asr_worker
from tars.meeting.config import _load_meeting_asr_config_base, load_meeting_asr_config, set_meeting_asr_runtime


@pytest.fixture(autouse=True)
def clear_config_cache():
    _load_meeting_asr_config_base.cache_clear()
    set_meeting_asr_runtime(None)
    yield
    _load_meeting_asr_config_base.cache_clear()
    set_meeting_asr_runtime(None)


def test_asr_worker_allows_hf_download(monkeypatch):
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    _init_asr_worker()
    assert os.environ.get("HF_HUB_OFFLINE") == "0"
    assert os.environ.get("TRANSFORMERS_OFFLINE") == "0"


def test_resolve_backend_sensevoice_offline_without_cache(monkeypatch):
    monkeypatch.setenv("TARS_MEETING_ASR_BACKEND", "sensevoice")
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    _load_meeting_asr_config_base.cache_clear()
    assert resolve_backend_name() == "whisper"


def test_should_fallback_to_whisper():
    from tars.meeting.asr.factory import _should_fallback_to_whisper

    err = "Cannot find an appropriate cached snapshot folder and outgoing traffic has been disabled"
    assert _should_fallback_to_whisper(err) is True


def test_resolve_backend_whisper_explicit(monkeypatch):
    monkeypatch.setenv("TARS_MEETING_ASR_BACKEND", "whisper")
    _load_meeting_asr_config_base.cache_clear()
    assert resolve_backend_name() == "whisper"


def test_display_model_name():
    name = display_model_name()
    assert name  # whisper-small or SenseVoiceSmall depending on backend


def test_sync_transcribe_missing_file():
    result = sync_transcribe("/nonexistent/audio.wav", "zh", "tiny")
    assert result["success"] is False
