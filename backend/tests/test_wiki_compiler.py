import pytest
from unittest.mock import AsyncMock
from tars.wiki.compiler import WikiCompiler
from tars.wiki.store import WikiStore


@pytest.fixture
def wiki_store(tmp_path):
    return WikiStore(wiki_dir=tmp_path)


@pytest.fixture
def compiler(wiki_store):
    mock_llm = AsyncMock()
    return WikiCompiler(store=wiki_store, llm_provider=mock_llm)


@pytest.mark.asyncio
async def test_compile_new_content_creates_page(compiler):
    compiler.llm_provider.return_value = (
        '{"action": "create", "page_name": "port-ops", '
        '"content": "# 港口运营\\n\\n泊位A已分配给XX轮", '
        '"summary": "港口运营相关知识"}'
    )
    result = await compiler.compile(
        source_text="今天泊位A分配给了XX轮",
        source_label="2026-05-25 周例会",
    )
    assert result.page_name == "port-ops"
    assert result.action == "create"
    assert compiler.store.read_page("port-ops") is not None


@pytest.mark.asyncio
async def test_compile_update_existing_page(compiler):
    compiler.store.write_page("port-ops", "# 港口运营\n\n旧内容")
    compiler.llm_provider.return_value = (
        '{"action": "update", "page_name": "port-ops", '
        '"content": "# 港口运营\\n\\n旧内容\\n\\n新增：泊位B开放", '
        '"summary": "港口运营相关知识"}'
    )
    result = await compiler.compile(
        source_text="泊位B今天开放了",
        source_label="运营通知",
    )
    assert result.action == "update"
    content = compiler.store.read_page("port-ops")
    assert "泊位B" in content


@pytest.mark.asyncio
async def test_compile_updates_index(compiler):
    compiler.llm_provider.return_value = (
        '{"action": "create", "page_name": "vessel-schedule", '
        '"content": "# 船舶调度\\n\\n内容", '
        '"summary": "船舶调度和排期信息"}'
    )
    await compiler.compile(source_text="XX轮明天到港", source_label="调度通知")
    index = compiler.store.read_index()
    assert "vessel-schedule" in index


@pytest.mark.asyncio
async def test_compile_preserves_existing_summaries(compiler):
    """Regression: compiling a new page must not lose other pages' summaries."""
    compiler.llm_provider.return_value = (
        '{"action": "create", "page_name": "port-ops", '
        '"content": "# 港口运营", "summary": "港口运营知识"}'
    )
    await compiler.compile(source_text="泊位A", source_label="s1")

    compiler.llm_provider.return_value = (
        '{"action": "create", "page_name": "vessel", '
        '"content": "# 船舶", "summary": "船舶调度信息"}'
    )
    await compiler.compile(source_text="XX轮", source_label="s2")

    index = compiler.store.read_index()
    assert "港口运营知识" in index
    assert "船舶调度信息" in index
