"""TaskDetector — 任务自动化意图检测器（v2.4）

三档触发：NONE（不触发）/ SOFT（LLM 自行判断）/ HARD（强制调用 task_planner）
"""
import re
from enum import Enum


TRIGGER_KEYWORDS = [
    "部署", "构建", "发布", "测试",
    "deploy", "build", "release", "test",
]

QUESTION_MARKERS = [
    "?", "？", "是什么", "为什么", "怎么回事", "是啥", "啥意思",
    "what", "why", "how", "怎样",
]


class TriggerMode(str, Enum):
    NONE = "none"   # 不触发
    SOFT = "soft"   # 让主 LLM 自己判断是否调 task_planner
    HARD = "hard"   # 强制在主 prompt 中注入 task_planner 调用指令


def detect_task_intent(user_msg: str, is_slash_plan: bool = False) -> TriggerMode:
    """分析用户消息，返回触发模式。

    /plan 命令 → HARD（零歧义，必定是执行意图）
    含关键词 + 长度>50 + 无疑问词 → HARD
    含关键词 + 长度>50 + 含疑问词 → SOFT（可能是询问）
    其他 → NONE
    """
    if is_slash_plan:
        return TriggerMode.HARD

    msg_lower = user_msg.lower()
    has_kw = any(kw in msg_lower for kw in TRIGGER_KEYWORDS)

    if not has_kw or len(user_msg) <= 10:
        return TriggerMode.NONE

    has_question = any(q in msg_lower for q in QUESTION_MARKERS)
    if has_question:
        return TriggerMode.SOFT

    return TriggerMode.HARD


def build_detector_prompt(user_msg: str, mode: TriggerMode) -> str:
    """根据触发模式生成注入到 system prompt 的提示"""
    if mode == TriggerMode.SOFT:
        return (
            "检测到可能的任务意图。"
            "若用户确实需要多步骤执行，可调用 task_planner 工具制定计划。"
        )
    if mode == TriggerMode.HARD:
        return (
            "检测到任务意图。"
            f"请调用 task_planner 工具为以下任务制定执行计划：{user_msg}"
        )
    return ""
