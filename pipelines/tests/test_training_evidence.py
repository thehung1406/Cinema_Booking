from argparse import Namespace

from ml.benchmark import training_command
from ml.train_sentiment import transformer_training_arguments


def test_segmenter_cannot_redirect_relative_training_output(tmp_path, monkeypatch):
    import os
    import sys
    from pathlib import Path
    from types import SimpleNamespace
    from ml.train_sentiment import load_segmenter
    original = Path.cwd()
    def create(**kwargs):
        os.chdir(tmp_path)
        return "segmenter"
    monkeypatch.setitem(sys.modules, "py_vncorenlp", SimpleNamespace(VnCoreNLP=create))
    assert load_segmenter(tmp_path) == "segmenter"
    assert Path.cwd() == original


def test_configured_learning_rate_reaches_trainer_without_rounding(tmp_path):
    config = {"training": dict(learning_rate=7e-6, weight_decay=.03, epochs=2,
        batch_size=2, gradient_accumulation_steps=3, max_length=128)}
    model = dict(checkpoint="test/model", revision="a"*40, preprocessing="normalize")
    command = training_command(config, model, "data", tmp_path, 17)
    args = Namespace(seed=17, epochs=2, batch_size=2, gradient_accumulation_steps=3,
        learning_rate=float(command[command.index("--learning-rate")+1]),
        weight_decay=float(command[command.index("--weight-decay")+1]))
    actual = transformer_training_arguments(args, tmp_path, False)
    assert actual["learning_rate"] == 7e-6
    assert actual["weight_decay"] == .03
    assert actual["num_train_epochs"] == 2


def test_lr_command_has_no_transformer_epoch_or_learning_rate(tmp_path):
    command = training_command({"training": {}}, {"backend": "sklearn"}, "data", tmp_path, 42)
    assert "--learning-rate" not in command and "--epochs" not in command


def test_tokenization_audit_does_not_count_exact_limit_as_truncation():
    from ml.tokenization_audit import length_statistics
    result = length_statistics([12, 256, 257], 256)
    assert result["over_max_length"] == 1
    assert result["truncation_rate"] == 1/3


def test_class_weight_objective_survives_single_item_microbatch():
    import torch
    from ml.train_sentiment import training_class_weights, weighted_classification_loss
    labels = ["negative"] * 8 + ["neutral"] + ["positive"]
    weights = training_class_weights(labels, "sqrt-balanced")
    assert abs(sum(weights[["negative", "neutral", "positive"].index(label)] for label in labels)/10 - 1) < 1e-9
    logits = torch.tensor([[1., 1., 1.]], requires_grad=True)
    loss = weighted_classification_loss(logits, torch.tensor([1]), weights)
    loss.backward()
    ordinary = torch.nn.functional.cross_entropy(logits.detach(), torch.tensor([1]))
    assert torch.isclose(loss.detach(), ordinary * weights[1])
    assert weights[1] > weights[0] and logits.grad[0, 1] < 0


def test_ablation_policy_reaches_training_command(tmp_path):
    config = {"training": dict(learning_rate=2e-5, epochs=3, batch_size=1,
        gradient_accumulation_steps=8, max_length=256, class_weight="sqrt-balanced")}
    command = training_command(config, dict(checkpoint="x", revision="a"*40,
        preprocessing="normalize"), "data", tmp_path, 42)
    assert command[command.index("--class-weight")+1] == "sqrt-balanced"


def test_predictor_segmenter_cannot_change_application_working_directory(tmp_path, monkeypatch):
    import importlib
    import json
    import os
    from pathlib import Path
    import sys
    from types import SimpleNamespace
    import pytest
    artifact=tmp_path/'artifact'
    artifact.mkdir()
    (artifact/'metadata.json').write_text(json.dumps(dict(model_version='test-only',
        text_preprocessing='vncorenlp',segmenter_path=str(tmp_path))))
    original=Path.cwd()
    def segmenter(**kwargs):
        os.chdir(tmp_path)
        return SimpleNamespace(word_segment=lambda text:[text])
    monkeypatch.setitem(sys.modules,'py_vncorenlp',SimpleNamespace(VnCoreNLP=segmenter))
    paths=[]
    def pipeline(*args,**kwargs):
        paths.append(kwargs['model'])
        return lambda *a,**k:[dict(label='negative',score=.1),dict(label='neutral',score=.2),dict(label='positive',score=.7)]
    monkeypatch.setitem(sys.modules,'transformers',SimpleNamespace(pipeline=pipeline))
    for name in ('ml.predictor','review_service.predictor'):
        module=importlib.import_module(name)
        module.load_predictor.cache_clear()
        predict, version=module.load_predictor('transformers',str(artifact))
        assert Path.cwd()==original
        assert version=='test-only' and predict('Fixture')['positive']==.7
        module.load_predictor.cache_clear()
    assert paths==[str(artifact.resolve())]*2
