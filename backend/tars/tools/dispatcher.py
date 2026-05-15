"""TARS Tools - 统一调度器
支持 LLM 原生 Function Calling + Prompt Fallback
"""
import json
import re
from typing import (
    Any, AsyncGenerator, Callable, Dict, List, Optional, Tuple,
)

from .base import BaseTool, ToolResult
from .registry import ToolRegistry


NATIVE_TOOL_MODELS = [
    "qwen3", "qwen2.5", "qwen2", "qwen-max", "qwen-plus", "qwen-turbo", "qwen-long",
    "llama3.1", "llama3.2", "llama3.3",
    "mistral", "mixtral", "command-r",
    "deepseek-chat", "deepseek-coder", "deepseek-v",
    "kimi",
]

TOOL_PROMPT_TEMPLATE = """## 可用工具

你可以调用以下工具来完成任务。需要调用工具时，请严格按照以下 JSON 格式输出（不要添加其他内容）：

```json
{{"tool_call": {{"name": "工具名", "arguments": {{参数对象}}}}}}
```

如果不需要调用工具，直接回答用户问题即可。

### 重要规则

- 用户要求"创建/生成/搭建/写好"某个项目（如"创建五子棋""搭建 FastAPI 脚手架"）时，必须调用 `task_planner` 制定计划，不要只输出步骤文字。
- 多文件、多步骤的落地任务（3 步以上）必须使用 `task_planner`，然后系统会自动执行计划。
- 单文件写入可直接调用 `file_write`，不需要 `task_planner`。
- 工具参数中的 `content` 字段可以包含完整代码（换行会被正确处理），不要截断。

### 工具列表

{tool_descriptions}
"""


class ToolDispatcher:
    """统一工具调度器"""

    def __init__(self, registry: ToolRegistry, provider=None):
        self.registry = registry
        self.provider = provider

    def set_provider(self, provider):
        self.provider = provider

    def supports_native_tools(self, model_name: str = "") -> bool:
        model_lower = model_name.lower()
        for prefix in NATIVE_TOOL_MODELS:
            if prefix in model_lower:
                return True
        return False

    async def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> ToolResult:
        tool = self.registry.get(tool_name)
        if not tool:
            return ToolResult(success=False, output="", error=f"工具 '{tool_name}' 不存在")
        try:
            merged_arguments = dict(arguments)
            for key, value in (context or {}).items():
                merged_arguments.setdefault(key, value)
            return await tool.execute(**merged_arguments)
        except Exception as e:
            return ToolResult(success=False, output="", error=f"工具执行失败: {e}")

    async def chat_with_tools(
        self,
        messages: List[Dict[str, Any]],
        model_name: str = "",
        stream: bool = True,
        on_tool_call: Optional[Callable] = None,
        on_tool_result: Optional[Callable] = None,
        max_rounds: int = 5,
        tools: Optional[List[Dict]] = None,
        response_format: Optional[Dict[str, Any]] = None,
        tool_context: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[str, None]:
        """带工具调用的对话，自动处理多轮工具调用循环。
        tools 参数可选，传入时覆盖默认的全部工具 schema。"""
        if not self.provider:
            raise RuntimeError("ToolDispatcher 未设置 provider")

        tools_schemas = tools if tools is not None else self.registry.get_function_schemas()
        use_native = self.supports_native_tools(model_name) and tools_schemas

        working_messages = list(messages)

        if not use_native and tools_schemas:
            working_messages = self._inject_tool_prompt(working_messages)

        tools_called = []
        for _ in range(max_rounds):
            if use_native:
                response = await self._call_with_native_tools(
                    working_messages, tools_schemas, stream, response_format=response_format
                )
            else:
                response = await self._call_with_prompt_fallback(
                    working_messages, stream, response_format=response_format
                )

            tool_call = self._extract_tool_call(response, use_native)

            if not tool_call:
                # 没有工具调用，输出最终文本
                text = self._extract_text(response, use_native)
                if text:
                    yield text
                    return
                if tools_called:
                    # LLM 未生成文本但之前调用了工具 → 兜底摘要
                    summary = "已执行: " + ", ".join(tools_called)
                    # 二次尝试：不带工具，只要求 LLM 根据工具结果总结
                    alt_msgs = list(working_messages)
                    alt_msgs.append({"role": "user", "content": "根据以上工具执行结果，请用简短中文总结完成情况。"})
                    try:
                        fallback2 = await self._call_with_prompt_fallback(alt_msgs, stream)
                        fb2_text = self._extract_text(fallback2, False)
                        if fb2_text and len(fb2_text) > 10:
                            yield fb2_text
                            return
                    except Exception:
                        pass
                    yield summary
                    return
                # LLM 完全无输出 → 降级重试（不带工具，避免工具过多导致卡死）
                if use_native and tools_schemas:
                    alt_msgs = list(working_messages)
                    # 移除系统消息中的工具描述以缩短 prompt
                    if alt_msgs and alt_msgs[0].get("role") == "system":
                        sys_content = alt_msgs[0]["content"]
                        # 截断工具部分
                        tool_idx = sys_content.find("## 可用工具")
                        if tool_idx > 0:
                            alt_msgs[0] = {**alt_msgs[0], "content": sys_content[:tool_idx].strip()}
                    try:
                        fallback = await self._call_with_prompt_fallback(alt_msgs, stream)
                        fb_text = self._extract_text(fallback, False)
                        if fb_text and len(fb_text) > 10:
                            yield fb_text
                            return
                    except Exception:
                        pass
                return

            tool_name, arguments = tool_call
            tools_called.append(tool_name)

            if on_tool_call:
                await on_tool_call(tool_name, arguments)

            result = await self.execute_tool(tool_name, arguments, context=tool_context)

            if on_tool_result:
                await on_tool_result(tool_name, result)

            # 将工具调用和结果加入消息历史
            if use_native:
                import uuid as _uuid
                call_id = f"call_{_uuid.uuid4().hex[:12]}"
                working_messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": call_id,
                        "type": "function",
                        "function": {"name": tool_name, "arguments": arguments},
                    }],
                })
                working_messages.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": result.output if result.success else (result.error or "执行失败"),
                })
            else:
                tool_msg = f"工具 `{tool_name}` 执行结果:\n{result.output if result.success else result.error}"
                working_messages.append({"role": "assistant", "content": f'```json\n{{"tool_call": {{"name": "{tool_name}", "arguments": {json.dumps(arguments, ensure_ascii=False)}}}}}\n```'})
                working_messages.append({"role": "user", "content": f"[系统] {tool_msg}\n\n请根据工具结果回答用户的问题。"})

        yield "[工具调用轮次已达上限]"

    def _inject_tool_prompt(self, messages: List[Dict]) -> List[Dict]:
        """为不支持 function calling 的模型注入工具提示到 system prompt"""
        tools = self.registry.list_all()
        if not tools:
            return messages

        descriptions = ""
        for tool in tools:
            descriptions += f"**{tool.name}**: {tool.description}\n"
            if tool.parameters_schema.get("properties"):
                descriptions += "参数:\n"
                for pname, pinfo in tool.parameters_schema["properties"].items():
                    required = pname in tool.parameters_schema.get("required", [])
                    req_mark = " (必填)" if required else ""
                    descriptions += f"  - {pname}{req_mark}: {pinfo.get('description', '')}\n"
            descriptions += "\n"

        tool_prompt = TOOL_PROMPT_TEMPLATE.format(tool_descriptions=descriptions)

        result = list(messages)
        if result and result[0].get("role") == "system":
            result[0] = {**result[0], "content": result[0]["content"] + "\n\n" + tool_prompt}
        else:
            result.insert(0, {"role": "system", "content": tool_prompt})
        return result

    async def _call_with_native_tools(
        self, messages: List[Dict], tools: List[Dict], stream: bool, response_format: Optional[Dict[str, Any]] = None
    ) -> Any:
        from ..models import ChatMessage
        chat_messages = []
        for m in messages:
            content = m.get("content")
            if content is None:
                content = ""
            chat_messages.append(ChatMessage(
                role=m["role"],
                content=content,
                tool_call_id=m.get("tool_call_id"),
                tool_calls=m.get("tool_calls"),
            ))

        response = await self.provider.chat(
            chat_messages,
            stream=False,
            tools=tools,
            response_format=response_format,
        )
        return response

    async def _call_with_prompt_fallback(
        self, messages: List[Dict], stream: bool, response_format: Optional[Dict[str, Any]] = None
    ) -> Any:
        from ..models import ChatMessage
        working_messages = list(messages)
        if response_format:
            working_messages = self._inject_response_format_prompt(working_messages, response_format)
        chat_messages = []
        for m in working_messages:
            content = m.get("content")
            if content is None:
                content = ""
            chat_messages.append(ChatMessage(role=m["role"], content=content))

        response = await self.provider.chat(
            chat_messages,
            stream=False,
            response_format=response_format,
        )
        return response

    def _inject_response_format_prompt(
        self,
        messages: List[Dict[str, Any]],
        response_format: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        schema = response_format.get("schema", {})
        format_type = response_format.get("type", "json_schema")
        schema_text = json.dumps(schema, ensure_ascii=False, indent=2) if schema else "{}"
        instruction = (
            "## 结构化输出要求\n\n"
            f"请严格输出 JSON，且必须符合以下 {format_type} 约束。\n"
            "不要输出额外解释、Markdown 或代码块。\n\n"
            f"{schema_text}"
        )

        result = list(messages)
        if result and result[0].get("role") == "system":
            result[0] = {**result[0], "content": result[0]["content"] + "\n\n" + instruction}
        else:
            result.insert(0, {"role": "system", "content": instruction})
        return result

    def _extract_tool_call(self, response: Any, native: bool) -> Optional[Tuple[str, Dict]]:
        """从响应中提取工具调用"""
        if native and isinstance(response, dict):
            tool_calls = response.get("tool_calls")
            if tool_calls:
                tc = tool_calls[0]
                func = tc.get("function", {})
                name = func.get("name", "")
                raw_args = func.get("arguments", "{}")
                if isinstance(raw_args, dict):
                    args = raw_args
                else:
                    try:
                        args = json.loads(raw_args)
                    except (json.JSONDecodeError, TypeError):
                        args = {}
                return (name, args)

        # Prompt fallback: 从文本中解析 JSON
        text = self._extract_text(response, native)
        if not text:
            return None
        return self._parse_tool_call_from_text(text)

    def _extract_text(self, response: Any, native: bool) -> str:
        if isinstance(response, str):
            return response

        if isinstance(response, dict):
            choices = response.get("choices", [])
            if choices:
                message = choices[0].get("message", {})
                content = message.get("content", "")
                if content:
                    return content

            content = response.get("content", "")
            if content:
                return content

        if hasattr(response, "content"):
            return getattr(response, "content", "") or ""

        return ""

    def _parse_tool_call_from_text(self, text: str) -> Optional[Tuple[str, Dict]]:
        """从文本中解析 JSON 格式的工具调用"""
        # 匹配 ```json ... ``` 块
        json_blocks = re.findall(r'```json\s*(.*?)\s*```', text, re.DOTALL)
        for block in json_blocks:
            try:
                data = json.loads(block)
                if "tool_call" in data:
                    tc = data["tool_call"]
                    return (tc.get("name", ""), tc.get("arguments", {}))
            except json.JSONDecodeError:
                continue

        # 用括号平衡法提取嵌套 JSON（正则无法处理嵌套大括号）
        extracted = self._extract_balanced_json(text, '"tool_call"')
        if extracted:
            return extracted

        return None

    def _extract_balanced_json(self, text: str, marker: str) -> Optional[Tuple[str, Dict]]:
        """用括号计数法从文本中提取包含 marker 的完整 JSON 对象"""
        idx = text.find(marker)
        if idx == -1:
            return None

        # 向前找到包含 marker 的 { 起始位置
        start = text.rfind('{', 0, idx)
        if start == -1:
            return None

        # 从 start 开始用括号计数找到匹配的 }
        depth = 0
        in_string = False
        escape_next = False
        for i in range(start, len(text)):
            ch = text[i]
            if escape_next:
                escape_next = False
                continue
            if ch == '\\' and in_string:
                escape_next = True
                continue
            if ch == '"' and not escape_next:
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    candidate = text[start:i + 1]
                    try:
                        data = json.loads(candidate)
                        if "tool_call" in data:
                            tc = data["tool_call"]
                            return (tc.get("name", ""), tc.get("arguments", {}))
                    except json.JSONDecodeError:
                        pass
                    return None
        return None
