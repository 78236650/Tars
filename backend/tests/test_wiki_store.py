import pytest
from pathlib import Path
from tars.wiki.store import WikiStore


@pytest.fixture
def wiki_store(tmp_path):
    return WikiStore(wiki_dir=tmp_path)


def test_init_creates_index(wiki_store, tmp_path):
    assert (tmp_path / "index.md").exists()


def test_write_page(wiki_store):
    wiki_store.write_page("port-ops", "# 港口运营\n\n泊位分配规则...")
    content = wiki_store.read_page("port-ops")
    assert "港口运营" in content


def test_read_nonexistent_page(wiki_store):
    assert wiki_store.read_page("nonexistent") is None


def test_list_pages(wiki_store):
    wiki_store.write_page("page-a", "# A")
    wiki_store.write_page("page-b", "# B")
    pages = wiki_store.list_pages()
    assert set(pages) == {"page-a", "page-b"}


def test_delete_page(wiki_store):
    wiki_store.write_page("temp", "# Temp")
    wiki_store.delete_page("temp")
    assert wiki_store.read_page("temp") is None


def test_update_index(wiki_store):
    wiki_store.write_page("vessel", "# 船舶调度")
    wiki_store.update_index({"vessel": "船舶调度相关知识"})
    index = wiki_store.read_index()
    assert "vessel" in index
