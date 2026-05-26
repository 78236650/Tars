from tars.tools.base import BaseTool, ToolResult
from tars.wiki.store import WikiStore


class WikiReadTool(BaseTool):
    name: str = "read_wiki"
    description: str = (
        "读取 wiki 中指定页面的完整内容。传入 page_name 获取具体页面，传入 'index' 获取所有页面索引。"
    )
    parameters_schema: dict = {
        "type": "object",
        "properties": {
            "page_name": {
                "type": "string",
                "description": "要读取的 wiki 页面名称，或 'index' 获取索引",
            },
        },
        "required": ["page_name"],
    }

    def __init__(self, store: WikiStore):
        self.store = store

    async def execute(self, **kwargs) -> ToolResult:
        page_name = kwargs.get("page_name", "index")

        if page_name == "index":
            content = self.store.read_index()
            return ToolResult(success=True, output=content)

        content = self.store.read_page(page_name)
        if content is None:
            pages = self.store.list_pages()
            return ToolResult(
                success=False,
                output=f"页面 '{page_name}' 不存在。可用页面: {', '.join(pages)}",
            )
        return ToolResult(success=True, output=content)
