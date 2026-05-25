"""Meeting summary LLM response parsing."""
from tars.tools.builtin.meeting_recognizer import _extract_chat_content


def test_extract_chat_content_from_openai_dict():
    assert _extract_chat_content({"content": "## 摘要\n内容", "model": "gpt-4"}) == "## 摘要\n内容"


def test_extract_chat_content_from_object():
    class R:
        content = "hello"

    assert _extract_chat_content(R()) == "hello"
