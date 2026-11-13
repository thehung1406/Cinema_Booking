import pytest

from ai_service import knowledge_retrieval
from ai_service.grounding import explicit_questions, support_spans


def test_two_interrogative_clauses_split_but_comparison_stays_together():
    assert explicit_questions("Pan hoạt động thế nào, và dùng thiết bị nào?") == (
        "Pan hoạt động thế nào?", "dùng thiết bị nào?",
    )
    comparison = "Pan và tilt khác nhau thế nào?"
    assert explicit_questions(comparison) == (comparison,)


def test_each_part_gets_a_slot_within_the_shared_limit(monkeypatch):
    left = [{"id": "book"}, {"id": "second-book-chunk"}, {"id": "third-book-chunk"}]
    right = [{"id": "book"}, {"id": "summary"}]
    monkeypatch.setattr(knowledge_retrieval, "retrieve", lambda db, query, **options:
                        right if query.startswith("dùng") else left)

    sources, state, queries = knowledge_retrieval.retrieve_knowledge(
        None, "Lia máy hoạt động thế nào, và dùng thiết bị nào?", "film_education", limit=2)

    assert state == "disabled"
    assert queries == ["Lia máy hoạt động thế nào? pan", "dùng thiết bị nào?"]
    assert [source["id"] for source in sources] == ["book", "summary"]


def test_support_preserves_the_antecedent_with_its_following_claim():
    spans = support_spans({"id": "doc:1", "text":
        "The example is Example Film. This movie illustrates lighting from below."})
    assert spans[1]["text"] == "The example is Example Film. This movie illustrates lighting from below."


@pytest.mark.parametrize("blocked", ["ambiguous", "conflict", "uncertain"])
def test_graph_can_block_a_combined_answer(monkeypatch, blocked):
    monkeypatch.setattr(knowledge_retrieval, "retrieve", lambda *args, **kwargs: [{"id": "text"}])
    monkeypatch.setattr(knowledge_retrieval, "graph_evidence", lambda db, graph, part, *args, **kwargs:
                        ([], blocked if part.startswith("Góc") else "no_match"))
    sources, state, _ = knowledge_retrieval.retrieve_knowledge(
        None, "Pan hoạt động thế nào? Góc máy đó dùng làm gì?", "film_education", graph=object())
    assert sources == [] and state == blocked
