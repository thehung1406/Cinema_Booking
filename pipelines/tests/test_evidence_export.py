import json

from ml.export_evidence import export


def test_unrun_models_are_planned_and_never_become_zero_scores(tmp_path):
    config = dict(models=[dict(id="lr", backend="sklearn", preprocessing="normalize")],
        datasets=[dict(id="missing", path="absent", status="needs-source")], seeds=[42],
        training=dict(epochs=3, learning_rate=2e-5, batch_size=1, gradient_accumulation_steps=8, max_length=256))
    source = tmp_path / "config.json"
    source.write_text(json.dumps(config), encoding="utf-8")
    report = export(source, tmp_path / "no-runs", tmp_path / "export")
    assert report["completed_runs"] == []
    assert report["validation_summary"] == []
    assert report["planned_models"][0]["epochs"] is None
    assert report["planned_models"][0]["learning_rate"] is None
    assert report["matrix"][0]["state"] == "blocked"
