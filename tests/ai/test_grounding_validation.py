import pytest

from ai_service import llm
from ai_service.graph import graph_evidence, merge_evidence
from ai_service.grounding import covers_specifics, support_spans
from ai_service.models import Base, utcnow
from ai_service.rag import upsert_document
from ai_service.schemas import GroundedAnswer
from sqlmodel import Session, create_engine


@pytest.mark.parametrize('question,evidence',[
    ('Sinh viên được giảm 50% không?','Người dùng thực hiện thanh toán qua giao diện.'),
    ('Hoàn tiền mấy ngày?','Trợ lý không được hứa hoàn tiền.'),
    ('Phim nào đoạt giải năm 2026?','Năm 2017 tác giả giới thiệu các thể loại phim.'),
    ('Số điện thoại hotline là gì?','Liên hệ bộ phận hỗ trợ.')])
def test_near_topic_is_not_evidence_for_missing_specific_facts(question,evidence):
    assert not covers_specifics(question,evidence)


def test_spelled_out_percent_is_still_a_specific_fact():
    assert not covers_specifics('Giá vé đã bao gồm thuế VAT mười phần trăm chưa?',
        'Người dùng thực hiện thanh toán qua giao diện của hệ thống.')


def test_pdf_layout_lines_are_joined_and_character_chunk_fragments_are_excluded():
    source=dict(id='doc:1',text='Incomplete ending. Genre groups\nfilms by recurring conventions. Unfinished tail',provenance={'character_start':1200})
    spans=support_spans(source)
    assert len(spans)==1 and spans[0]['text']=='Genre groups films by recurring conventions.'


def test_graph_only_excerpt_in_a_later_chunk_keeps_its_first_sentence():
    excerpt = "A pan turns the camera horizontally."

    class Graph:
        release_id = "release"

        def find(self, question, scope, releases):
            assert releases == ["release"]
            return [dict(graph_release="release", source_id="book", version="1", checksum="checksum",
                         block_index=0, page=5, excerpt=excerpt, concept_id="pan", predicate="definition",
                         qualifier="", status="verified", value="horizontal rotation", matched_aliases=["lia may"],
                         alias_method="exact", alias_score=1.0, claim_id="pan-definition")]

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        upsert_document(db, dict(source_id="book", title="Film book", version="1", source_url="/film",
                                 effective_at=utcnow(), approved=True,
                                 provenance={"checksum": "checksum", "scope": "film_education"},
                                 blocks=[{"text": "x" * 1200 + "Partial sentence. " + excerpt, "page_start": 5}]))
        sources, state = graph_evidence(db, Graph(), "Lia máy là gì?", "film_education")
    assert state == "matched"
    source, = sources
    assert source["provenance"]["character_start"] == 1200
    assert [span["text"] for span in support_spans(source)] == [excerpt]
    lexical = source | {"text": "Partial sentence. " + excerpt}
    combined, = merge_evidence([lexical], sources, state, 3)
    assert [span["text"] for span in support_spans(combined)] == [excerpt]


def test_supported_numeric_policy_can_pass_conservative_check():
    assert covers_specifics('Ghế được giữ bao nhiêu phút?','Thời gian giữ ghế là 5 phút.')


def test_fabricated_support_span_is_rejected_even_with_a_real_citation_id(monkeypatch):
    monkeypatch.setattr(llm,'structured',lambda *a,**k:GroundedAnswer(decision='answer', clarification='', sentences=[dict(
        text='Unsupported claim.',source_id='doc:1:span:999')]))
    trace={}
    with pytest.raises(ValueError,match='invented'):
        llm.grounded_answer(None,'What is genre?',[dict(id='doc:1',text='Genre groups films by recurring conventions.')],trace=trace)


def test_missing_year_abstains_before_model_call(monkeypatch):
    monkeypatch.setattr(llm,'structured',lambda *a,**k:pytest.fail('Should not call the model'))
    trace={}
    assert llm.grounded_answer(None,'Who won in 2026?',[dict(id='doc:1',text='This book was published in 2017.')],trace=trace)==''
    assert trace['grounding_validation']['model_called'] is False


def test_missing_scene_context_gets_a_focused_followup_without_evidence(monkeypatch):
    monkeypatch.setattr(llm, "structured", lambda *a, **k: pytest.fail("Should not call the model"))
    reply = llm.grounded_reply(None, "Tôi nên chọn góc máy nào cho cảnh này?", [])
    assert reply.status == "needs_clarification"
    assert "cảm giác" in reply.text


def test_question_echo_is_rejected_even_if_its_citation_exists(monkeypatch):
    monkeypatch.setattr(llm, "structured", lambda *a, **k: GroundedAnswer(
        decision="answer", clarification="", sentences=[
            dict(text="Dolly có thể làm lộ điều gì.", source_id="doc:1:span:0"),
        ]))
    reply = llm.grounded_reply(None, "Dolly có thể làm lộ điều gì?",
                               [dict(id="doc:1", text="A dolly can reveal scenery.")])
    assert reply.status == "no_evidence"


def test_policy_returns_exact_quote_only_after_grounding(monkeypatch):
    source = dict(id="doc:1", text="Thời gian giữ ghế là 5 phút. Xem hướng dẫn thanh toán.")
    monkeypatch.setattr(llm, "structured", lambda *a, **k: GroundedAnswer(
        decision="answer", clarification="", sentences=[
            dict(text="Ghế được giữ trong 5 phút.", source_id="doc:1:span:0"),
        ]))
    reply = llm.grounded_reply(None, "Ghế được giữ bao nhiêu phút?", [source], extractive=True)
    assert reply.text == "Thời gian giữ ghế là 5 phút. [doc:1]"
    assert reply.source_ids == ("doc:1",)
    monkeypatch.setattr(llm, "structured", lambda *a, **k: GroundedAnswer(
        decision="insufficient", clarification="Đổi hình thức thanh toán được không?" * 10, sentences=[]))
    assert llm.grounded_reply(None, "Đổi hình thức thanh toán được không?", [source], extractive=True).status == "no_evidence"


def test_extractive_answer_rejects_a_faq_question_as_the_quote(monkeypatch):
    source = dict(id="doc:1", text="Có đổi vé sau khi đặt không? Vé đã thanh toán không được đổi.")
    monkeypatch.setattr(llm, "structured", lambda *a, **k: GroundedAnswer(
        decision="answer", clarification="", sentences=[
            dict(text="Vé đã thanh toán không được đổi.", source_id="doc:1:span:0"),
        ]))
    reply = llm.grounded_reply(None, "Vé đã mua có đổi được không?", [source], extractive=True)
    assert reply.status == "no_evidence" and reply.source_ids == ()


def test_generated_answer_cannot_add_an_unsupported_number(monkeypatch):
    monkeypatch.setattr(llm, "structured", lambda *a, **k: GroundedAnswer(
        decision="answer", clarification="", sentences=[
            dict(text="Có 2 loại nguồn sáng.", source_id="doc:1:span:0"),
        ]))
    assert llm.grounded_reply(None, "Nguồn sáng nào được dùng?",
                              [dict(id="doc:1", text="Phần này nói về nguồn sáng chính.")]).status == "no_evidence"


def test_two_separate_questions_require_support_for_each(monkeypatch):
    responses = iter([
        GroundedAnswer(decision="answer", clarification="", sentences=[
            dict(text="Pan là lia máy.", source_id="doc:1:span:0"),
        ]),
        GroundedAnswer(decision="insufficient", clarification="", sentences=[]),
    ])
    monkeypatch.setattr(llm, "structured", lambda *a, **k: next(responses))
    trace = {}
    reply = llm.grounded_reply(None, "Pan là gì? Hộp đựng làm bằng gì?",
                               [dict(id="doc:1", text="Pan is a camera movement.")], trace=trace)
    assert reply.status == "no_evidence" and reply.source_ids == ()
    assert trace["parts"][0]["grounding_validation"]["accepted"]
    assert trace["grounding_validation"]["reason"] == "part_missing_support_or_context"
