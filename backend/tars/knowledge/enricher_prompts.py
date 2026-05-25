"""分类型 enrich prompt 模板 — metrics 文档不走通用 prompt。"""
from __future__ import annotations

from typing import Any, Dict

PROMPT_SCHEMA = """
只返回 JSON，不要解释文字。格式：
{
  "title": "...",
  "one_liner": "<= 80 字一句话",
  "summary": "200-600 字结构化摘要",
  "key_points": ["要点1", "要点2"],
  "key_facts": ["数字/规则/例外"],
  "tags": ["标签"],
  "qa_pairs": [{"question":"","answer":""}],
  "glossary": [{"term":"","definition":""}]
}
"""


def build_policy_prompt(*, sample: str, file_name: str) -> str:
    return (
        "你是企业制度文档理解助手。请提取适用范围、审批权限、流程步骤与例外条款。\n"
        f"{PROMPT_SCHEMA}\n"
        f"文档类型：policy（制度）\n"
        f"文件名：{file_name}\n"
        "----\n"
        f"{sample}\n"
    )


def build_proposal_prompt(*, sample: str, file_name: str) -> str:
    return (
        "你是方案/汇报文档理解助手。请提取背景、目标、方案要点、里程碑与风险。\n"
        f"{PROMPT_SCHEMA}\n"
        f"文档类型：proposal（方案/汇报）\n"
        f"文件名：{file_name}\n"
        "----\n"
        f"{sample}\n"
    )


def build_generic_prompt(*, sample: str, file_name: str, doc_type: str = "generic") -> str:
    return (
        "你是文档理解助手。请基于下列文档内容产出结构化 JSON 摘要。\n"
        f"{PROMPT_SCHEMA}\n"
        f"文档类型：{doc_type}\n"
        f"文件名：{file_name}\n"
        "----\n"
        f"{sample}\n"
    )


def build_map_prompt(*, section_title: str, section_text: str, doc_type: str) -> str:
    return (
        f"文档类型：{doc_type}。请仅针对章节「{section_title}」输出 JSON：\n"
        '{"section_summary":"...", "key_facts":["..."]}\n'
        "只返回 JSON。\n"
        "----\n"
        f"{section_text}\n"
    )


def build_reduce_prompt(*, doc_type: str, file_name: str, map_results: str) -> str:
    return (
        "以下是一篇长文档各章节的局部摘要，请合并为整篇文档画像。\n"
        f"{PROMPT_SCHEMA}\n"
        f"文档类型：{doc_type}\n"
        f"文件名：{file_name}\n"
        "----\n"
        f"{map_results}\n"
    )


def get_prompt_builder(doc_type: str):
    builders = {
        "policy": build_policy_prompt,
        "proposal": build_proposal_prompt,
    }
    return builders.get(doc_type, build_generic_prompt)


def build_enrich_prompt(
    *,
    doc_type: str,
    sample: str,
    file_name: str,
) -> str:
    builder = get_prompt_builder(doc_type)
    if builder is build_generic_prompt:
        return builder(sample=sample, file_name=file_name, doc_type=doc_type)
    return builder(sample=sample, file_name=file_name)
