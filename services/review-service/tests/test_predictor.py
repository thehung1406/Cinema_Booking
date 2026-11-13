import json
import sys
from types import SimpleNamespace

import pytest

from review_service import predictor


def test_transformer_demo_checks_token_limit_before_classification(tmp_path, monkeypatch):
    (tmp_path / "metadata.json").write_text(
        json.dumps({"model_version": "demo", "max_length": 4}), encoding="utf-8"
    )
    classified = []

    def tokenize(text, *, truncation, verbose):
        assert truncation is False
        return {"input_ids": [0] + text.split() + [2]}

    def classify(text, *, top_k, truncation, max_length):
        assert top_k is None and max_length == 4
        classified.append((text, truncation))
        return [{"label": "neutral", "score": 1.0}]

    monkeypatch.setitem(sys.modules, "transformers", SimpleNamespace(
        pipeline=lambda *args, **kwargs: classify
    ))
    classify.tokenizer = tokenize
    try:
        predict, _ = predictor.load_predictor("transformers", str(tmp_path), reject_truncation=True)
        assert predict("hay   lắm") == {"neutral": 1.0}
        with pytest.raises(predictor.InputTooLong):
            predict("hay   lắm luôn")
        assert classified == [("hay lắm", False)]

        worker_predict, _ = predictor.load_predictor("transformers", str(tmp_path))
        assert worker_predict("hay lắm luôn") == {"neutral": 1.0}
        assert classified[-1] == ("hay lắm luôn", True)
    finally:
        predictor.load_predictor.cache_clear()
