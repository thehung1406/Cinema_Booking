import json

import pytest

from ml.blind_annotation import prepare, reconcile
from ml.data import read_jsonl, write_jsonl


def row(index, label=None, reviewer=None):
    return dict(id=f"test-fixture-{index}", text=f"Test fixture content {index}",
        source="https://example.com/test", license="test-only", group_id=str(index), synthetic=False,
        label=label, reviewer=reviewer, review_status="approved" if label else "pending",
        annotation_origin="manual-tool-confirmation")


def test_blind_passes_hide_hints_and_never_create_human_decisions(tmp_path):
    source = tmp_path / "source.jsonl"
    write_jsonl(source, [row(i) | dict(suggested_label=label, platform="test", suggestion_source="test-only")
        for i, label in enumerate(("negative", "neutral", "positive"))])
    out = tmp_path / "batch"
    prepare(source, out, per_label=1)
    a, b = (read_jsonl(out / f"pass-{p}-pending.jsonl") for p in ("A", "B"))
    assert {r["id"] for r in a} == {r["id"] for r in b}
    assert all(r["label"] is None and r["reviewer"] is None and "suggested_label" not in r for r in a + b)
    report, agreed, conflicts = reconcile(out / "pass-A-pending.jsonl", out / "pass-B-pending.jsonl")
    assert report["cohen_kappa"] is None and report["double_confirmed"] == 0
    assert not agreed and not conflicts
    with pytest.raises(ValueError, match="overwrite"):
        prepare(source, out, 1)


def test_agreement_is_computed_before_adjudication_and_disputes_stay_pending(tmp_path):
    first, second = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    write_jsonl(first, [row(i, label, "Person A") for i, label in enumerate(["negative", "negative", "positive", "positive"])])
    write_jsonl(second, [row(i, label, "Person B") for i, label in enumerate(["negative", "negative", "positive", "negative"])])
    result, agreed, conflicts = reconcile(first, second)
    assert result["raw_agreement"] == .75 and result["cohen_kappa"] == .5
    assert len(agreed) == 3 and len(conflicts) == 1
    assert conflicts[0]["label"] is None and conflicts[0]["review_status"] == "pending"
    write_jsonl(second, [row(i, "negative", "person a") for i in range(4)])
    with pytest.raises(ValueError, match="independent people"):
        reconcile(first, second)


def test_changed_source_is_rejected_even_when_both_people_agree(tmp_path):
    first, second = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    write_jsonl(first, [row(0, "positive", "A")])
    write_jsonl(second, [row(0, "positive", "B") | {"text": "Different source"}])
    with pytest.raises(ValueError, match="changed"):
        reconcile(first, second)


def test_adjudication_requires_a_third_person_and_preserves_first_two_decisions(tmp_path):
    from ml.blind_annotation import accept_adjudications
    conflict=row(0) | dict(first_label='positive',second_label='negative',first_reviewer='A',second_reviewer='B')
    path=tmp_path/'adjudicated.jsonl'
    decision=conflict | dict(label='negative',reviewer='A',review_status='approved',
        annotation_origin='manual-adjudication',annotation_note='Test fixture reason')
    write_jsonl(path,[decision])
    with pytest.raises(ValueError,match='third reviewer'):
        accept_adjudications([conflict],path)
    write_jsonl(path,[decision | {'reviewer':'C'}])
    assert accept_adjudications([conflict],path)[0]['label']=='negative'
