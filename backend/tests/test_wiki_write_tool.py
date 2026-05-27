import pytest
from tars.wiki.store import WikiStore
from tars.tools.builtin.wiki_write import WikiWriteTool


@pytest.fixture
def tool(tmp_path):
    return WikiWriteTool(store=WikiStore(wiki_dir=tmp_path))


@pytest.mark.asyncio
async def test_write_creates_page_and_index(tool):
    result = await tool.execute(
        page_name="customer-notes",
        content="# 客户备注\n\n重要联系人：张三",
        summary="客户备注与联系人",
    )
    assert result.success
    assert tool.store.read_page("customer-notes") is not None
    assert "customer-notes" in tool.store.read_index()


@pytest.mark.asyncio
async def test_write_rejects_index(tool):
    result = await tool.execute(page_name="index", content="# bad")
    assert not result.success


@pytest.mark.asyncio
async def test_write_rejects_invalid_name(tool):
    result = await tool.execute(page_name="Bad Name", content="# x")
    assert not result.success
