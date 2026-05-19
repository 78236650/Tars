"""Knowledge citation fields in search results."""
from tars.knowledge.access import enrich_hit, format_citation_results


def test_enrich_hit_adds_citation_fields():
    hit = enrich_hit({
        "id": "doc_meeting_1_summary_chunk_0",
        "text": "讨论了知识库集成。",
        "source": {"file_name": "周会纪要", "collection_id": "coll-1"},
        "metadata": {},
        "score": 0.9,
    })
    cite = hit["citation"]
    assert cite["doc_id"] == "doc_meeting_1_summary"
    assert cite["doc_title"] == "周会纪要"
    assert cite["source"] == "meeting"


def test_format_citation_results_includes_ref_token():
    ranked = [enrich_hit({
        "id": "doc_a_chunk_0",
        "text": "hello",
        "source": {"file_name": "notes.md"},
        "metadata": {},
    })]
    text = format_citation_results(ranked)
    assert "ref:doc_a" in text
    assert "notes.md" in text
