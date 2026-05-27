import json
import logging
from dataclasses import dataclass
from typing import Callable, Awaitable

from tars.wiki.store import WikiStore

logger = logging.getLogger(__name__)

COMPILE_PROMPT_TEMPLATE = """\
你是知识编辑者，负责将新素材整合进 wiki。

当前 wiki 索引：
{index}

当前已有页面列表：{pages}

新素材来源：{source_label}
新素材内容：
{source_text}

请决定如何处理这段素材。返回 JSON（不要 markdown 代码块）：
{{
  "action": "create" 或 "update",
  "page_name": "页面文件名（英文短横线命名）",
  "content": "完整的页面 Markdown 内容（如果 update 则包含合并后的完整内容）",
  "summary": "一句话描述这个页面的内容（用于 index）"
}}

规则：
- 如果素材属于已有页面的主题，选择 update 并合并内容
- 如果是全新主题，选择 create
- 页面内容要结构化、有标题层级
- 在页面末尾的"来源追溯"段落记录本次更新来源
"""


@dataclass
class CompileResult:
    action: str
    page_name: str
    summary: str


class WikiCompiler:
    def __init__(self, store: WikiStore, llm_provider: Callable[..., Awaitable[str]]):
        self.store = store
        self.llm_provider = llm_provider

    async def compile(self, source_text: str, source_label: str) -> CompileResult:
        index = self.store.read_index()
        pages = self.store.list_pages()

        prompt = COMPILE_PROMPT_TEMPLATE.format(
            index=index,
            pages=", ".join(pages) if pages else "(空)",
            source_label=source_label,
            source_text=source_text[:3000],
        )

        raw = await self.llm_provider(prompt)
        data = json.loads(raw)

        self.store.write_page(data["page_name"], data["content"])

        all_summaries: dict[str, str] = {}
        self._merge_index_summaries(all_summaries, data["page_name"], data["summary"])

        return CompileResult(
            action=data["action"],
            page_name=data["page_name"],
            summary=data["summary"],
        )

    def _merge_index_summaries(self, summaries: dict, new_page: str, new_summary: str) -> None:
        existing_index = self.store.read_index()
        for line in existing_index.splitlines():
            if line.startswith("- **["):
                try:
                    name = line.split("[")[1].split("]")[0]
                    summary = line.split("—")[-1].strip()
                    if name != new_page:
                        summaries[name] = summary
                except (IndexError, ValueError):
                    pass
        summaries[new_page] = new_summary
        self.store.update_index(summaries)
