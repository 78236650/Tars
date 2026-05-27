import re

from tars.tools.base import BaseTool, ToolResult
from tars.wiki.store import WikiStore

_PAGE_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class WikiWriteTool(BaseTool):
    name: str = "write_wiki"
    description: str = (
        "将内容写入或更新 wiki 页面（Markdown）。用户要求保存到 wiki、更新 wiki 知识页时使用。"
        "page_name 使用英文短横线命名（如 port-ops、meeting-0525）。"
    )
    parameters_schema: dict = {
        "type": "object",
        "properties": {
            "page_name": {
                "type": "string",
                "description": "wiki 页面文件名（英文短横线，勿用 index）",
            },
            "content": {
                "type": "string",
                "description": "完整 Markdown 页面内容",
            },
            "summary": {
                "type": "string",
                "description": "一句话摘要，用于 index；可省略则从正文首行推断",
            },
        },
        "required": ["page_name", "content"],
    }

    def __init__(self, store: WikiStore):
        self.store = store

    def _upsert_index_summary(self, page_name: str, summary: str) -> None:
        summaries: dict[str, str] = {}
        for line in self.store.read_index().splitlines():
            if line.startswith("- **["):
                try:
                    name = line.split("[")[1].split("]")[0]
                    summaries[name] = line.split("—")[-1].strip()
                except (IndexError, ValueError):
                    pass
        summaries[page_name] = summary
        self.store.update_index(summaries)

    async def execute(self, **kwargs) -> ToolResult:
        page_name = (kwargs.get("page_name") or "").strip().lower()
        content = (kwargs.get("content") or "").strip()
        summary = (kwargs.get("summary") or "").strip()

        if page_name == "index":
            return ToolResult(success=False, output="不能写入保留页 index，请使用其他 page_name。")
        if not page_name or not _PAGE_NAME_RE.match(page_name):
            return ToolResult(
                success=False,
                output="page_name 无效：请使用英文小写与短横线，例如 customer-notes、port-ops。",
            )
        if not content:
            return ToolResult(success=False, output="content 不能为空。")

        if not summary:
            for line in content.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    summary = line[:120]
                    break
                if line.startswith("#"):
                    summary = line.lstrip("#").strip()[:120]
                    break
            summary = summary or page_name.replace("-", " ")

        existed = self.store.read_page(page_name) is not None
        self.store.write_page(page_name, content)
        self._upsert_index_summary(page_name, summary)

        action = "更新" if existed else "创建"
        return ToolResult(
            success=True,
            output=f"已{action} wiki 页面 '{page_name}'。可在知识库 Wiki Tab 或 read_wiki 查看。",
        )
