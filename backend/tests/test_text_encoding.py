"""Tests for UTF-8 mojibake repair."""
from tars.utils.text_encoding import repair_mojibake


def test_repair_latin1_mojibake():
    garbled = "接口调用日志表".encode("utf-8").decode("latin-1")
    assert repair_mojibake(garbled) == "接口调用日志表"


def test_repair_leaves_valid_cjk():
    assert repair_mojibake("接口调用日志表") == "接口调用日志表"


def test_repair_leaves_ascii():
    assert repair_mojibake("api_call_log") == "api_call_log"
