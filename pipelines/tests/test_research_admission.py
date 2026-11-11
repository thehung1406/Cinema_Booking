import json
from pathlib import Path

from ml.benchmark import matrix, summarize
from ml.data import write_jsonl
from ml.dataset_audit import audit


def dataset(tmp_path):
    for split in ("train", "validation", "test"):
        write_jsonl(tmp_path / f"{split}.jsonl", [dict(id=f"{split}-{label}",
            text=f"{split} unique content for {label}", label=label, group_id=f"{split}-{label}",
            source="unit-test", license="test-only", review_status="approved", reviewer="fixture")
            for label in ("negative", "neutral", "positive")])


def test_cross_split_duplicates_and_synthetic_data_are_not_admitted(tmp_path):
    dataset(tmp_path)
    assert audit(tmp_path)["admissible"]
    rows = [json.loads(line) for line in (tmp_path / "test.jsonl").read_text().splitlines()]
    rows[0]["text"] = "train unique content for negative"
    rows[1]["synthetic"] = True
    write_jsonl(tmp_path / "test.jsonl", rows)
    report = audit(tmp_path)
    assert not report["admissible"]
    assert any("leakage" in issue for issue in report["problems"])
    assert any("Synthetic" in issue for issue in report["problems"])


def test_missing_data_and_unpinned_model_stay_blocked(tmp_path):
    config = {"datasets": [{"id": "missing", "path": "absent", "status": "needs-labels"}],
              "models": [{"id": "encoder", "checkpoint": "test/model", "revision": None}], "seeds": [42]}
    rows = matrix(config, tmp_path)
    assert rows[0]["state"] == "blocked" and len(rows[0]["issues"]) == 2
    assert summarize(tmp_path, tmp_path / "summary.json") == []
    assert json.loads((tmp_path / "summary.json").read_text())["results"] == []
