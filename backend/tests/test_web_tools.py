"""Web Search + Web Fetch 工具测试"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch, AsyncMock, MagicMock


class TestWebSearch:
    @pytest.mark.asyncio
    async def test_empty_query_rejected(self):
        from tars.tools.builtin.web_search import WebSearchTool
        tool = WebSearchTool()
        result = await tool.execute(query="")
        assert result.success is False
        assert "关键词" in result.error

    @pytest.mark.asyncio
    async def test_search_parses_results(self):
        from tars.tools.builtin.web_search import WebSearchTool
        tool = WebSearchTool()

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value={
            "results": [
                {"title": "FastAPI", "url": "https://fastapi.tiangolo.com", "content": "FastAPI framework"},
                {"title": "Tutorial", "url": "https://example.com/t", "content": "Step by step guide"},
            ]
        })

        async def mock_get(*args, **kwargs):
            return mock_resp

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = mock_get
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            result = await tool.execute(query="FastAPI")

        assert result.success is True
        assert "FastAPI" in result.output
        assert "https://fastapi.tiangolo.com" in result.output
        assert "共 2 条" in result.output
        assert result.metadata["count"] == 2

    @pytest.mark.asyncio
    async def test_no_results(self):
        from tars.tools.builtin.web_search import WebSearchTool
        tool = WebSearchTool()

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value={"results": []})

        async def mock_get(*args, **kwargs):
            return mock_resp

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = mock_get
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            result = await tool.execute(query="xyz")

        assert result.success is True
        assert "未找到" in result.output

    @pytest.mark.asyncio
    async def test_connection_error(self):
        from tars.tools.builtin.web_search import WebSearchTool
        import httpx
        tool = WebSearchTool()

        async def mock_get(*args, **kwargs):
            raise httpx.ConnectError("connection refused")

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = mock_get
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            result = await tool.execute(query="test")

        assert result.success is False
        assert "SearXNG" in result.error
        assert "docker run" in result.error

    @pytest.mark.asyncio
    async def test_limit_clamped(self):
        from tars.tools.builtin.web_search import WebSearchTool
        tool = WebSearchTool()

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        results = [{"title": f"r{i}", "url": f"u{i}", "content": f"c{i}"} for i in range(20)]
        mock_resp.json = MagicMock(return_value={"results": results})

        async def mock_get(*args, **kwargs):
            return mock_resp

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = mock_get
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            result = await tool.execute(query="test", limit=50)

        assert result.metadata["count"] == 10


class TestWebFetch:
    @pytest.mark.asyncio
    async def test_empty_url_rejected(self):
        from tars.tools.builtin.web_fetch import WebFetchTool
        tool = WebFetchTool()
        result = await tool.execute(url="")
        assert result.success is False

    @pytest.mark.asyncio
    async def test_fetch_extracts_text(self):
        from tars.tools.builtin.web_fetch import WebFetchTool
        tool = WebFetchTool()

        html = """
        <html><head><title>Test Article</title></head>
        <body>
            <nav>navigation menu</nav>
            <article>
                <h1>Main Heading</h1>
                <p>This is the main content of the article. It has enough text to pass the 100 char threshold for trafilatura extraction. We need more content here to ensure successful extraction by the readability algorithm.</p>
                <p>Another paragraph with more substantial text content.</p>
            </article>
            <footer>copyright</footer>
        </body></html>
        """

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html

        async def mock_get(*args, **kwargs):
            return mock_resp

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = mock_get
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            result = await tool.execute(url="https://example.com/article")

        assert result.success is True
        assert "main content" in result.output.lower()
        assert "navigation" not in result.output.lower() or "menu" not in result.output.lower()

    @pytest.mark.asyncio
    async def test_url_auto_https(self):
        from tars.tools.builtin.web_fetch import WebFetchTool
        tool = WebFetchTool()

        captured_url = {}
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html><body><p>" + "x" * 200 + "</p></body></html>"

        async def mock_get(url, **kwargs):
            captured_url["value"] = url
            return mock_resp

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = mock_get
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            await tool.execute(url="example.com")

        assert captured_url["value"].startswith("https://")
