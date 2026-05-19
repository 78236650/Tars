"""Tests for meeting summary LLM response parsing."""
import pytest

from tars.tools.builtin.meeting_recognizer import MeetingRecognizerTool


@pytest.fixture
def tool():
    return MeetingRecognizerTool(provider=None)


class TestParseSummaryResponse:
    def test_extracts_content_field_from_python_dict_repr(self, tool):
        raw = """{'content': '## 会议信息
- 主题：测试

## 核心摘要
正文'}"""
        result = tool._parse_summary_response(raw)
        assert "## 会议信息" in result["summary"]
        assert "- 主题：测试" in result["summary"]
        assert "'content'" not in result["summary"]

    def test_extracts_json_summary_field(self, tool):
        raw = '{"summary": "## 核心摘要\\n\\n结论", "key_points": ["a", "b"]}'.replace("\\n", "\n")
        # Valid JSON requires escaped newlines in the string literal
        import json
        raw = json.dumps({"summary": "## 核心摘要\n\n结论", "key_points": ["a", "b"]}, ensure_ascii=False)
        result = tool._parse_summary_response(raw)
        assert result["summary"].startswith("## 核心摘要")
        assert result["key_points"] == ["a", "b"]

    def test_plain_markdown_passthrough(self, tool):
        raw = "## 核心摘要\n\n- 要点一\n\n这是正文。"
        result = tool._parse_summary_response(raw, markdown_mode=True)
        assert result["summary"] == raw
        assert len(result["key_points"]) >= 1

    def test_coerce_dict_provider_output(self, tool):
        assert tool._coerce_llm_text({"content": "## 标题\n内容"}) == "## 标题\n内容"
