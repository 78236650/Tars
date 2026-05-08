"""Scene Analyzer — v2.2 异步场景分析器"""
import asyncio
import json
import re
from datetime import datetime, timezone, timedelta
from typing import Optional

from tars.config.memory import config
from tars.memory.working_context import WorkingContextManager

SCENE_PROMPT = """分析本轮对话，输出严格 JSON。不要任何额外文字。

最近 3 轮摘要: {recent_summary}
当前 Working Context: {working_ctx}
用户消息: {user_msg}
助手回复: {assistant_msg}

输出格式:
{{
  "intent": "coding.debug|planning.decompose|writing.draft|research.search|data.analyze|casual|meta|unknown",
  "intent_confidence": 0.0-1.0,
  "entities_mentioned": [{{"name":"...","type":"person|project|tech|concept|org","is_new":true|false}}],
  "topic_shift": true|false,
  "open_thread_refs": ["话题1"],
  "needs_memory_recall": true|false,
  "recall_hints": ["关键词1"]
}}

意图标签: coding.write|debug|review|refactor|explain, planning.decompose|estimate|prioritize, writing.draft|edit|translate|summarize, research.search|compare|learn, data.analyze|transform|visualize, casual, meta, unknown

如果对话是闲聊 (casual)，needs_memory_recall=false。
只输出 JSON。"""


class SceneAnalyzer:
    """每轮对话结束后异步分析，产出下一轮的 Working Context"""

    def __init__(self, provider, wc: WorkingContextManager, db):
        self.provider = provider
        self.wc = wc
        self.db = db

    def try_fast_path(self, session_id: str, user_msg: str, wc: dict) -> Optional[dict]:
        """快速路径：消息短 + 无topic信号 + WC新鲜 → 复用上轮"""
        if not user_msg:
            return None
        # 短消息 < 50 字符
        if len(user_msg) > 50:
            return None
        # 不含话题切换关键词
        shift_keywords = ["另外", "换个话题", "对了", "?", "？", "新任务"]
        if any(kw in user_msg for kw in shift_keywords):
            return None
        # WC 更新时间 < 5 分钟
        try:
            updated = wc.get("updated_at", "")
            if updated:
                from datetime import datetime, timezone, timedelta
                ts = datetime.fromisoformat(updated)
                now = datetime.now(timezone(timedelta(hours=8)))
                if (now - ts).total_seconds() > 300:
                    return None
            else:
                return None
        except Exception:
            return None
        # 快路径命中
        snapshot = wc.get("last_scene_snapshot", {})
        if snapshot and snapshot.get("intent"):
            print(f"[SceneAnalyzer] fast_path=hit msg_len={len(user_msg)}")
            return snapshot
        return None

    async def analyze(self, session_id: str, user_msg: str, assistant_msg: str) -> Optional[dict]:
        """分析本轮对话，结果写入 WC。先 fast_path 再 LLM。"""
        try:
            wc = self.wc.get(session_id)

            # 快速路径跳过
            fast = self.try_fast_path(session_id, user_msg, wc)
            if fast:
                self.wc.update(session_id, last_scene_snapshot=fast)
                return fast

            recent = self._get_recent_summary(session_id, 3)

            prompt = SCENE_PROMPT.format(
                recent_summary=recent,
                working_ctx=json.dumps(wc, ensure_ascii=False),
                user_msg=user_msg[:2000],
                assistant_msg=assistant_msg[:2000],
            )

            from tars.models import ChatMessage
            msgs = [ChatMessage(role="user", content=prompt)]
            resp = await asyncio.wait_for(
                self.provider.chat(msgs, stream=False, temperature=0.1),
                timeout=config.scene_timeout_ms / 1000.0,
            )

            text = resp.content if hasattr(resp, "content") else str(resp)
            scene = self._parse_json(text)
            if scene:
                self.wc.set_scene_result(session_id, scene)
                ms = 0  # approximate
                print(f"[SceneAnalyzer] intent={scene.get('intent')} conf={scene.get('intent_confidence')} "
                      f"entities={len(scene.get('entities_mentioned',[]))} shift={scene.get('topic_shift')}")
                return scene
            else:
                print(f"[SceneAnalyzer] JSON 解析失败，原文: {text[:100]}")

        except asyncio.TimeoutError:
            print(f"[SceneAnalyzer] 超时 ({config.scene_timeout_ms}ms)")
        except Exception as e:
            print(f"[SceneAnalyzer] 失败: {e}")

        return None

    @staticmethod
    def _parse_json(text: str) -> Optional[dict]:
        text = text.strip()
        try:
            data = json.loads(text)
            if isinstance(data, dict) and "intent" in data:
                return data
        except json.JSONDecodeError:
            pass
        m = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
        m = re.search(r'\{[^{}]*"intent"[^{}]*\}', text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        return None

    def _get_recent_summary(self, session_id: str, n: int = 3) -> str:
        msgs = self.db.get_messages(session_id)[-n*2:]
        lines = []
        for m in msgs:
            role = "U" if m.role == "user" else "A"
            lines.append(f"[{role}] {m.content[:200]}")
        return "\n".join(lines)
