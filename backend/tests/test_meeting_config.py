"""Meeting ASR config loader tests."""
import os

import pytest

from tars.meeting.config import (
    _load_meeting_asr_config_base,
    load_meeting_asr_config,
    resolve_asr_language,
    resolve_whisper_device,
    resolve_whisper_model_path,
    set_meeting_asr_runtime,
)


@pytest.fixture(autouse=True)
def clear_config_cache():
    _load_meeting_asr_config_base.cache_clear()
    set_meeting_asr_runtime(None)
    yield
    _load_meeting_asr_config_base.cache_clear()
    set_meeting_asr_runtime(None)


def test_default_model_is_small():
    cfg = load_meeting_asr_config()
    assert cfg["model"] == "small"
    assert cfg["language_default"] == "zh"
    assert cfg["output_script"] == "simplified"
    assert cfg.get("backend") == "whisper"
    assert (cfg.get("preprocess") or {}).get("enabled") is True


def test_env_override_model(monkeypatch):
    monkeypatch.setenv("TARS_MEETING_ASR_MODEL", "medium")
    _load_meeting_asr_config_base.cache_clear()
    cfg = load_meeting_asr_config()
    assert cfg["model"] == "medium"


def test_resolve_asr_language():
    assert resolve_asr_language("auto") is None
    assert resolve_asr_language("zh") == "zh"
    assert resolve_asr_language("en") == "en"
    assert resolve_asr_language("EN-US") == "en"


def test_resolve_whisper_model_path_when_downloaded():
    path = resolve_whisper_model_path()
    if path is None:
        pytest.skip("whisper-small not downloaded locally")
    import os

    assert os.path.isfile(os.path.join(path, "model.bin"))


def test_runtime_whisper_model_override():
    set_meeting_asr_runtime({"model": "medium"})
    cfg = load_meeting_asr_config()
    assert cfg["model"] == "medium"


def test_resolve_whisper_device_cpu():
    device, compute = resolve_whisper_device({"device": "cpu", "compute_type": "int8"})
    assert device == "cpu"
    assert compute == "int8"
