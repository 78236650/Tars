import pytest
from unittest.mock import AsyncMock
from tars.wiki.router import WikiRagRouter


@pytest.fixture
def router():
    return WikiRagRouter(llm_provider=None)


def test_large_file_routes_to_rag(router):
    result = router.route(page_count=20, text_size=80000, file_name="report.pdf", file_format="pdf")
    assert result == "rag"


def test_small_markdown_routes_to_wiki(router):
    result = router.route(page_count=2, text_size=3000, file_name="notes.md", file_format="md")
    assert result == "wiki"


def test_meeting_minutes_routes_to_wiki(router):
    result = router.route(page_count=5, text_size=8000, file_name="2026-05-25-周例会纪要.md", file_format="md")
    assert result == "wiki"


def test_academic_paper_routes_to_rag(router):
    result = router.route(page_count=12, text_size=40000, file_name="paper.pdf", file_format="pdf", has_abstract=True)
    assert result == "rag"


def test_user_override_respected(router):
    result = router.route(page_count=100, text_size=200000, file_name="huge.pdf", file_format="pdf", user_override="wiki")
    assert result == "wiki"


def test_ambiguous_file_returns_llm_decide(router):
    result = router.route(page_count=8, text_size=25000, file_name="brief.pdf", file_format="pdf")
    assert result == "llm_decide"


@pytest.mark.asyncio
async def test_llm_fallback_decision():
    mock_llm = AsyncMock(return_value="wiki")
    router = WikiRagRouter(llm_provider=mock_llm)
    result = await router.route_with_llm_fallback(
        page_count=8, text_size=25000, file_name="brief.pdf",
        file_format="pdf", text_preview="行业简报：2026年Q2港口吞吐量..."
    )
    assert result in ("wiki", "rag")
    mock_llm.assert_called_once()
