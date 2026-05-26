import pytest
from tars.wiki.store import WikiStore
from tars.tools.builtin.wiki_read import WikiReadTool


@pytest.fixture
def wiki_store(tmp_path):
    store = WikiStore(wiki_dir=tmp_path)
    store.write_page("port-ops", "# 港口运营\n\n泊位分配规则...")
    store.update_index({"port-ops": "港口运营相关知识"})
    return store


@pytest.fixture
def tool(wiki_store):
    return WikiReadTool(store=wiki_store)


@pytest.mark.asyncio
async def test_read_existing_page(tool):
    result = await tool.execute(page_name="port-ops")
    assert result.success
    assert "港口运营" in result.output


@pytest.mark.asyncio
async def test_read_nonexistent_page(tool):
    result = await tool.execute(page_name="nonexistent")
    assert not result.success
    assert "不存在" in result.output


@pytest.mark.asyncio
async def test_read_index(tool):
    result = await tool.execute(page_name="index")
    assert result.success
    assert "port-ops" in result.output


def test_tool_schema(tool):
    schema = tool.to_function_schema()
    assert schema["function"]["name"] == "read_wiki"
    assert "page_name" in schema["function"]["parameters"]["properties"]
