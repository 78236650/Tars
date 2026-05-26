import pytest
from unittest.mock import AsyncMock
from tars.wiki.events import WikiEventHandler
from tars.wiki.compiler import WikiCompiler
from tars.wiki.store import WikiStore


@pytest.fixture
def handler(tmp_path):
    store = WikiStore(wiki_dir=tmp_path)
    mock_llm = AsyncMock(return_value=(
        '{"action": "create", "page_name": "meeting-0525", '
        '"content": "# 会议纪要 2026-05-25\\n\\n决策要点...", '
        '"summary": "2026-05-25 周例会纪要"}'
    ))
    compiler = WikiCompiler(store=store, llm_provider=mock_llm)
    return WikiEventHandler(compiler=compiler)


@pytest.mark.asyncio
async def test_on_meeting_ended(handler):
    await handler.on_meeting_ended(
        transcript="今天讨论了泊位分配问题，决定A泊位给XX轮...",
        meeting_title="2026-05-25 周例会",
    )
    page = handler.compiler.store.read_page("meeting-0525")
    assert page is not None
