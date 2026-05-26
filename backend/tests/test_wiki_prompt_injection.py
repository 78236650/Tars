from tars.wiki.store import WikiStore


def test_wiki_index_injection_format(tmp_path):
    store = WikiStore(wiki_dir=tmp_path)
    store.write_page("port-ops", "# 港口运营")
    store.update_index({"port-ops": "港口运营相关知识"})

    index_content = store.read_index()
    assert "port-ops" in index_content
    assert len(index_content) < 5000
