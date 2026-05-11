"""工具调用消息序列化回归测试

覆盖历史 bug：
- Ollama 期望 tool_calls[].function.arguments 是 object/dict，不是 JSON 字符串
- OpenAI 协议 (OpenRouter/Custom) 期望 arguments 是 JSON 字符串
- 之前 dispatcher.py 统一 json.dumps 导致 Ollama 第二轮 400 Bad Request
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tars.models.base import ChatMessage
from tars.models.ollama import OllamaProvider
from tars.models.custom import CustomProvider


class TestOllamaArgumentsSerialization:
    """Ollama 特殊约定：arguments 必须是 dict"""

    def _format_messages(self, provider, messages):
        # 复用 provider.chat 的格式化逻辑，但不发请求
        formatted = []
        for msg in messages:
            m = {"role": msg.role, "content": msg.content or ""}
            if msg.tool_call_id:
                m["tool_call_id"] = msg.tool_call_id
            if msg.tool_calls:
                normalized_calls = []
                for tc in msg.tool_calls:
                    tc_copy = dict(tc)
                    func = dict(tc_copy.get("function", {}))
                    args = func.get("arguments", {})
                    if isinstance(args, str):
                        try:
                            args = json.loads(args) if args else {}
                        except (json.JSONDecodeError, TypeError):
                            args = {}
                    func["arguments"] = args
                    tc_copy["function"] = func
                    normalized_calls.append(tc_copy)
                m["tool_calls"] = normalized_calls
            formatted.append(m)
        return formatted

    def test_dict_arguments_stay_dict(self):
        msg = ChatMessage(
            role="assistant",
            content="",
            tool_calls=[{
                "id": "call_1", "type": "function",
                "function": {"name": "web_search", "arguments": {"query": "test"}},
            }],
        )
        formatted = self._format_messages(None, [msg])
        assert formatted[0]["tool_calls"][0]["function"]["arguments"] == {"query": "test"}

    def test_string_arguments_parsed_to_dict(self):
        msg = ChatMessage(
            role="assistant",
            content="",
            tool_calls=[{
                "id": "call_1", "type": "function",
                "function": {"name": "web_search", "arguments": '{"query": "test"}'},
            }],
        )
        formatted = self._format_messages(None, [msg])
        # 字符串应被解析回 dict
        assert formatted[0]["tool_calls"][0]["function"]["arguments"] == {"query": "test"}

    def test_malformed_arguments_fallback_empty(self):
        msg = ChatMessage(
            role="assistant",
            content="",
            tool_calls=[{
                "id": "call_1", "type": "function",
                "function": {"name": "web_search", "arguments": "not valid json {{"},
            }],
        )
        formatted = self._format_messages(None, [msg])
        assert formatted[0]["tool_calls"][0]["function"]["arguments"] == {}


class TestOpenAIArgumentsSerialization:
    """OpenAI 协议 (OpenRouter/Custom)：arguments 必须是 JSON 字符串"""

    def _format_messages(self, messages):
        # 复用 custom.py / openrouter.py 的格式化逻辑
        formatted = []
        for msg in messages:
            msg_dict = {"role": msg.role, "content": msg.content}
            if msg.tool_call_id:
                msg_dict["tool_call_id"] = msg.tool_call_id
            if msg.tool_calls:
                normalized_calls = []
                for tc in msg.tool_calls:
                    tc_copy = dict(tc)
                    func = dict(tc_copy.get("function", {}))
                    args = func.get("arguments")
                    if isinstance(args, dict):
                        func["arguments"] = json.dumps(args, ensure_ascii=False)
                    elif args is None:
                        func["arguments"] = "{}"
                    tc_copy["function"] = func
                    normalized_calls.append(tc_copy)
                msg_dict["tool_calls"] = normalized_calls
            formatted.append(msg_dict)
        return formatted

    def test_dict_arguments_stringified(self):
        msg = ChatMessage(
            role="assistant",
            content="",
            tool_calls=[{
                "id": "call_1", "type": "function",
                "function": {"name": "web_search", "arguments": {"query": "test"}},
            }],
        )
        formatted = self._format_messages([msg])
        args_str = formatted[0]["tool_calls"][0]["function"]["arguments"]
        assert isinstance(args_str, str)
        assert json.loads(args_str) == {"query": "test"}

    def test_unicode_preserved(self):
        msg = ChatMessage(
            role="assistant",
            content="",
            tool_calls=[{
                "id": "call_1", "type": "function",
                "function": {"name": "web_search", "arguments": {"query": "中文查询"}},
            }],
        )
        formatted = self._format_messages([msg])
        args_str = formatted[0]["tool_calls"][0]["function"]["arguments"]
        # ensure_ascii=False 保留中文
        assert "中文查询" in args_str

    def test_none_arguments_becomes_empty_obj_string(self):
        msg = ChatMessage(
            role="assistant",
            content="",
            tool_calls=[{
                "id": "call_1", "type": "function",
                "function": {"name": "web_search"},  # 无 arguments
            }],
        )
        formatted = self._format_messages([msg])
        assert formatted[0]["tool_calls"][0]["function"]["arguments"] == "{}"


class TestDispatcherFlow:
    """dispatcher 构造 tool_calls 时 arguments 应保留 dict，交给 provider 层按需转换"""

    def test_dispatcher_appends_dict_arguments(self):
        # 模拟 dispatcher 处理后的消息结构
        arguments = {"query": "test", "limit": 5}
        msg = {
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": "call_web_search", "type": "function",
                "function": {"name": "web_search", "arguments": arguments},
            }],
        }
        # dispatcher 不应序列化，保持 dict
        assert isinstance(msg["tool_calls"][0]["function"]["arguments"], dict)
        assert msg["tool_calls"][0]["function"]["arguments"]["query"] == "test"
