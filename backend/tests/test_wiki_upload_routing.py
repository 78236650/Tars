from tars.wiki.router import WikiRagRouter


def test_upload_routing_integration():
    router = WikiRagRouter(llm_provider=None)

    assert router.route(page_count=3, text_size=2000, file_name="周例会纪要.md", file_format="md") == "wiki"
    assert router.route(page_count=50, text_size=100000, file_name="industry-report.pdf", file_format="pdf") == "rag"
    assert router.route(page_count=1, text_size=500, file_name="quick-note.txt", file_format="txt") == "wiki"
    assert router.route(
        page_count=12, text_size=45000, file_name="paper.pdf", file_format="pdf", has_abstract=True
    ) == "rag"
