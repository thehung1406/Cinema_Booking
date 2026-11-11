import pytest

from ai_service import llm
from ai_service.grounding import covers_specifics
from ai_service.schemas import GroundedAnswer


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
    from ai_service.grounding import support_spans
    source=dict(id='doc:1',text='Incomplete ending. Genre groups\nfilms by recurring conventions. Unfinished tail',provenance={'character_start':1200})
    spans=support_spans(source)
    assert len(spans)==1 and spans[0]['text']=='Genre groups films by recurring conventions.'


def test_supported_numeric_policy_can_pass_conservative_check():
    assert covers_specifics('Ghế được giữ bao nhiêu phút?','Thời gian giữ ghế là 5 phút.')


def test_fabricated_support_span_is_rejected_even_with_a_real_citation_id(monkeypatch):
    monkeypatch.setattr(llm,'structured',lambda *a,**k:GroundedAnswer(sentences=[dict(
        text='Unsupported claim.',source_id='doc:1:span:999')]))
    trace={}
    with pytest.raises(ValueError,match='invented'):
        llm.grounded_answer(None,'What is genre?',[dict(id='doc:1',text='Genre groups films by recurring conventions.')],trace=trace)


def test_missing_year_abstains_before_model_call(monkeypatch):
    monkeypatch.setattr(llm,'structured',lambda *a,**k:pytest.fail('Should not call the model'))
    trace={}
    assert llm.grounded_answer(None,'Who won in 2026?',[dict(id='doc:1',text='This book was published in 2017.')],trace=trace)==''
    assert trace['grounding_validation']['model_called'] is False
