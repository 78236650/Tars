"""TARS Agent v2 - 使用 ToolDispatcher 的新 Agent"""
import os
import json
import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta

from ..models import LLMProvider, OllamaProvider, CustomProvider, ChatMessage
from ..database import Database
from ..memory import MemoryManager
from ..channels import Channel
from ..workspace import WorkspaceManager
from ..tools import ToolRegistry, ToolDispatcher, registry as global_tool_registry
from ..skills import SkillRegistry, skill_registry as global_skill_registry, SkillExecutor
from .subagent_manager import SubAgentManager


MULTIMODAL_MODELS = ["llava", "bakllava", "llama3.2-vision", "minicpm-v", "qwen2-vl", "qwen-vl"]


def now_iso():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


class AgentV2:
    """重构后的 Agent，使用 ToolDispatcher 进行工具调用"""

    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        db: Optional[Database] = None,
        workspace: Optional[WorkspaceManager] = None,
        tool_registry: Optional[ToolRegistry] = None,
        skill_registry: Optional[SkillRegistry] = None,
        file_storage=None,
        file_parser=None,
        memory_manager=None,
        task_executor=None,
    ):
        self.db = db or Database()
        self.workspace = workspace or WorkspaceManager()
        self.current_model: str = os.getenv("OLLAMA_MODEL", "llama3.2")
        self.subagent_manager = SubAgentManager(self)

        self.tool_registry = tool_registry or global_tool_registry
        self.skill_registry = skill_registry or global_skill_registry
        self.skill_executor = SkillExecutor(self.skill_registry)

        self.file_storage = file_storage
        self.file_parser = file_parser
        self.task_executor = task_executor

        if provider:
            self.provider = provider
        else:
            self.provider = self._create_default_provider()

        # 记忆管理器（新版，支持 LLM 提取 + 语义搜索）
        self.memory_manager = memory_manager or MemoryManager(self.db, provider=self.provider)

        self.dispatcher = ToolDispatcher(self.tool_registry, self.provider)

    def _create_default_provider(self) -> LLMProvider:
        provider_type = os.getenv("LLM_PROVIDER", "ollama").lower()
        if provider_type == "openrouter":
            from ..models import OpenRouterProvider
            return OpenRouterProvider()
        return OllamaProvider(model=self.current_model)

    def switch_model(self, model_name: str) -> bool:
        try:
            self.provider = OllamaProvider(model=model_name)
            self.current_model = model_name
            self.dispatcher.set_provider(self.provider)
            return True
        except Exception:
            return False

    def switch_to_custom_model(self, model_id: str, base_url: str, model: str, api_key: str = None) -> bool:
        try:
            self.provider = CustomProvider(base_url=base_url, model=model, api_key=api_key)
            self.current_model = model
            self.dispatcher.set_provider(self.provider)
            return True
        except Exception:
            return False

    async def get_available_models(self) -> List[str]:
        try:
            return await self.provider.list_models()
        except Exception:
            return []

    async def handle_message(self, session_id: str, user_content: str, channel: Channel, file_ids: Optional[List[str]] = None):
        """处理用户消息 - 使用 ToolDispatcher，支持文件附件"""
        # 1. 获取或创建会话
        session = self.db.get_session(session_id)
        if not session:
            session = self.db.create_session()
            session_id = session.id

        # 2. 保存用户消息
        self.db.add_message(session_id, "user", user_content)

        # 3. 获取历史消息
        history = self.db.get_messages(session_id)

        # 4. 获取记忆上下文
        memory_context = self.memory_manager.get_context_for_query(user_content)

        # 5. 构建 system prompt（含人格 + 记忆 + PromptSkill）
        system_prompt = self.workspace.build_context()
        prompt_injection = self.skill_executor.build_prompt_injection()
        if prompt_injection:
            system_prompt += f"\n\n{prompt_injection}"
        if memory_context:
            system_prompt += f"\n\n{memory_context}"

        # 6. 构建消息列表
        messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})

        # 7. 处理文件附件
        if file_ids and self.file_storage and self.file_parser:
            await channel.send(session_id, {
                "type": "file_processing",
                "session_id": session_id,
                "message": "正在解析文件...",
                "timestamp": now_iso(),
            })
            user_msg = await self._build_message_with_files(session_id, user_content, file_ids, channel)
            messages[-1] = user_msg  # 替换最后一条用户消息

        # 8. 定义工具调用回调
        used_web_flag = {"value": False}

        async def on_tool_call(tool_name: str, arguments: Dict):
            if tool_name in ("web", "web_search", "web_fetch"):
                used_web_flag["value"] = True
            await channel.send(session_id, {
                "type": "tool_calling",
                "session_id": session_id,
                "tool": tool_name,
                "parameters": arguments,
                "timestamp": now_iso(),
            })

        async def on_tool_result(tool_name: str, result):
            await channel.send(session_id, {
                "type": "tool_result",
                "session_id": session_id,
                "tool": tool_name,
                "success": result.success,
                "output": result.output,
                "error": result.error,
                "timestamp": now_iso(),
            })

        # 8. 调用 ToolDispatcher
        full_response = ""
        try:
            async for chunk in self.dispatcher.chat_with_tools(
                messages=messages,
                model_name=self.current_model,
                stream=True,
                on_tool_call=on_tool_call,
                on_tool_result=on_tool_result,
            ):
                full_response += chunk
                await channel.send(session_id, {
                    "type": "text_chunk",
                    "session_id": session_id,
                    "content": chunk,
                    "timestamp": now_iso(),
                    "model": self.current_model,
                })
        except Exception as e:
            await channel.send(session_id, {
                "type": "error",
                "session_id": session_id,
                "message": f"处理失败: {e}",
                "code": "agent_error",
                "timestamp": now_iso(),
            })
            return

        # 8.5 检查是否有待执行的计划（task_planner 被调用时）
        if self.task_executor:
            planner_tool = self.tool_registry.get("task_planner")
            if planner_tool and hasattr(planner_tool, "pop_pending_plan"):
                plan = planner_tool.pop_pending_plan()
                if plan:
                    await self.task_executor.execute(plan, session_id, channel)

        # 9. 保存助手响应
        self.db.add_message(session_id, "assistant", full_response)

        # 10. 反思记忆（V3 异步非阻塞，不延迟 done 事件）
        async def _reflect_background():
            try:
                applied = await self.memory_manager.reflect(
                    user_content,
                    full_response,
                    used_web=used_web_flag["value"],
                )
            except Exception as e:
                print(f"[Agent] 反思失败: {e}")
                applied = []
            if applied:
                await channel.send(session_id, {
                    "type": "memory_extracted",
                    "session_id": session_id,
                    "memories": [{"op": op.get("op"), "summary": str(op)[:80]} for op in applied],
                    "timestamp": now_iso(),
                })

        asyncio.create_task(_reflect_background())

        # 11. 完成
        await channel.send(session_id, {
            "type": "done",
            "session_id": session_id,
            "timestamp": now_iso(),
            "model": self.current_model,
        })

    def get_subagent_info(self) -> dict:
        return self.subagent_manager.get_all_subagents()

    def update_subagent_config(self, agent_type: str, config: dict) -> bool:
        return self.subagent_manager.update_subagent_config(agent_type, config)

    # ========= 多模态文件处理 =========

    def _is_multimodal(self) -> bool:
        model_lower = self.current_model.lower()
        return any(m in model_lower for m in MULTIMODAL_MODELS)

    async def _build_message_with_files(
        self, session_id: str, user_content: str, file_ids: List[str], channel: Channel
    ) -> Dict[str, Any]:
        """解析文件并构建带附件的用户消息"""
        text_parts = [user_content] if user_content else []
        images = []
        is_multimodal = self._is_multimodal()

        for file_id in file_ids:
            record = self.file_storage.get(file_id)
            if not record:
                text_parts.append(f"[文件 {file_id} 不存在]")
                continue

            parsed = await self.file_parser.parse(record)

            if parsed.type == "image":
                if is_multimodal and parsed.image_base64:
                    images.append(parsed.image_base64)
                else:
                    # 非多模态：发 warning + 用 OCR 文本
                    await channel.send(session_id, {
                        "type": "warning",
                        "session_id": session_id,
                        "message": "当前模型不支持图片理解，已使用 OCR 提取文字。建议切换到多模态模型（如 llava）获得更好效果。",
                        "timestamp": now_iso(),
                    })
                    if parsed.ocr_text:
                        text_parts.append(f"\n\n---\n[图片 OCR: {record.name}]\n{parsed.ocr_text}")
                    else:
                        text_parts.append(f"\n\n---\n[图片: {record.name}]（无法提取文字，建议切换到多模态模型）")
            else:
                # 文档类：附加文本
                if parsed.text:
                    truncated_note = "（内容过长已截断）" if parsed.truncated else ""
                    text_parts.append(f"\n\n---\n[文件: {record.name}]{truncated_note}\n{parsed.text}")

        content = "\n".join(text_parts)
        msg: Dict[str, Any] = {"role": "user", "content": content}
        if images:
            msg["images"] = images
        return msg

