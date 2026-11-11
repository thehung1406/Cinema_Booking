"""Train TF-IDF/LR or segmented PhoBERT; test data is never used for selection."""
import argparse
import json
import platform
import math
import os
import re
import subprocess
import time
from pathlib import Path
from ml.text import normalize_text
from ml.data import load_splits, fingerprint
from ml.task_spec import label_order

LABELS = ["negative", "neutral", "positive"]


def training_class_weights(labels, policy, labels_order=LABELS):
    """Fit on train only; E_train[w_y] = 1, including for batch size one."""
    from collections import Counter
    counts = Counter(labels)
    if policy == "none":
        return [1.0] * len(labels_order)
    if policy != "sqrt-balanced" or any(not counts[label] for label in labels_order):
        raise ValueError("Class weights require all train classes and a supported policy")
    raw = [math.sqrt(len(labels) / counts[label]) for label in labels_order]
    mean = sum(counts[label] * weight for label, weight in zip(labels_order, raw)) / len(labels)
    return [weight / mean for weight in raw]


def weighted_classification_loss(logits, labels, weights):
    import torch
    # Weighted mean CE would cancel weights when microbatch=1. Divide by sample
    # count instead, so gradient accumulation approximates E[w_y * CE].
    return torch.nn.functional.cross_entropy(logits, labels,
        weight=logits.new_tensor(weights), reduction="sum") / labels.numel()


def load_segmenter(path):
    import py_vncorenlp
    original = Path.cwd()
    try:
        return py_vncorenlp.VnCoreNLP(save_dir=str(Path(path).resolve()), annotators=["wseg"])
    finally:
        # py_vncorenlp 0.1.4 changes global cwd; relative output/data must stay stable.
        os.chdir(original)


def transformer_training_arguments(args, output, cuda):
    """Single source of truth shared by Trainer and its recorded configuration."""
    return dict(output_dir=str(output / "checkpoints"), seed=args.seed, data_seed=args.seed,
        num_train_epochs=args.epochs, per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size, gradient_accumulation_steps=args.gradient_accumulation_steps,
        fp16=cuda, learning_rate=args.learning_rate, weight_decay=args.weight_decay,
        optim="adamw_torch", eval_strategy="epoch", save_strategy="epoch", load_best_model_at_end=True,
        metric_for_best_model="macro_f1", greater_is_better=True, save_total_limit=1, report_to=[])


def architecture_metadata(model):
    config = model.config
    return dict(model_type=config.model_type, implementation=type(model).__name__,
        encoder_layers=getattr(config, "num_hidden_layers", None), hidden_size=getattr(config, "hidden_size", None),
        attention_heads=getattr(config, "num_attention_heads", None), num_labels=config.num_labels,
        total_parameters=sum(p.numel() for p in model.parameters()),
        trainable_parameters=sum(p.numel() for p in model.parameters() if p.requires_grad))


def metrics(y, predictions, labels=LABELS):
    from sklearn.metrics import classification_report, confusion_matrix, f1_score
    if set(y) - set(labels) or set(predictions) - set(labels):
        raise ValueError('Prediction/gold outside declared label space')
    return {"macro_f1": f1_score(y, predictions, labels=labels, average="macro", zero_division=0),
            "per_class": classification_report(y, predictions, labels=labels, output_dict=True, zero_division=0),
            "confusion_matrix": confusion_matrix(y, predictions, labels=labels).tolist(), "label_order": list(labels)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True); p.add_argument("--output", required=True)
    p.add_argument("--backend", choices=["sklearn", "transformers"], default="sklearn")
    p.add_argument("--model", default="vinai/phobert-base")
    p.add_argument("--revision", help="Pin a Hugging Face commit SHA for reproducible downloads")
    p.add_argument("--segmenter-path"); p.add_argument("--seed", type=int, default=42)
    p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--learning-rate", type=float, default=2e-5)
    p.add_argument("--weight-decay", type=float, default=0.0)
    p.add_argument("--class-weight", choices=["none", "sqrt-balanced"], default="none")
    p.add_argument("--preprocessing", choices=["normalize", "vncorenlp"], default="vncorenlp")
    p.add_argument("--max-length", type=int, default=256)
    p.add_argument("--batch-size", type=int, default=1)
    p.add_argument("--gradient-accumulation-steps", type=int, default=8)
    args = p.parse_args()
    if (not 8 <= args.max_length <= 256 or args.batch_size < 1 or args.gradient_accumulation_steps < 1
            or args.epochs < 1 or not math.isfinite(args.learning_rate) or args.learning_rate <= 0
            or not math.isfinite(args.weight_decay) or args.weight_decay < 0):
        raise ValueError("Invalid training settings")
    from ml.dataset_audit import audit
    admission = audit(args.data)
    if not admission["admissible"]:
        raise ValueError("Dataset rejected: " + "; ".join(admission["problems"]))
    splits = load_splits(args.data)
    train_prepared(args,splits)


def train_prepared(args, splits, *, supervision='publisher-or-human-reviewed'):
    """Shared fitting implementation. Callers must validate their explicit protocol.

    Primary CLI above still requires audit() + load_splits() human/publisher gates.
    The separate four-dataset CLI permits honest silver training only when its
    descriptor declares weak supervision and validation/evaluation remain human.
    """
    started = time.perf_counter()
    labels=list(label_order(args.data))
    for name, rows in splits.items():
        if {r['label'] for r in rows} != set(labels):
            raise ValueError(f"{name} must include every class; collect additional independent groups")
    out = Path(args.output); out.mkdir(parents=True, exist_ok=False)
    train, val = splits["train"], splits["validation"]
    x, vx = [normalize_text(r["text"]) for r in train], [normalize_text(r["text"]) for r in val]
    y, vy = [r["label"] for r in train], [r["label"] for r in val]
    if args.backend == "sklearn":
        if args.class_weight != "none":
            raise ValueError("--class-weight is a transformer ablation; LR already uses balanced weights")
        import joblib
        from sklearn.pipeline import Pipeline
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        candidates = []
        for c in (.25, 1, 4):
            model = Pipeline([("tfidf", TfidfVectorizer(analyzer="char", ngram_range=(2, 5), min_df=1)),
                              ("classifier", LogisticRegression(C=c, max_iter=1000, class_weight="balanced", random_state=args.seed))])
            model.fit(x, y)
            predictions = model.predict(vx)
            report = metrics(vy, predictions, labels)
            candidates.append((report["macro_f1"], c, model, report, predictions))
        _, best_c, model, report, predictions = max(candidates, key=lambda item: item[0])
        report["selected_C"] = best_c
        joblib.dump(model, out / "model.joblib")
        classifier = model.named_steps["classifier"]
        architecture = dict(model_type="tfidf-logistic-regression", implementation=type(classifier).__name__,
            encoder_layers=None, total_parameters=int(classifier.coef_.size + classifier.intercept_.size),
            trainable_parameters=int(classifier.coef_.size + classifier.intercept_.size),
            input_features=len(model.named_steps["tfidf"].vocabulary_), analyzer="char", ngram_range=[2, 5])
        actual_training = dict(learning_rate=None, epochs_requested=None, epochs_completed=None,
            batch_size=None, effective_batch_size=None, max_length=None, optimizer="lbfgs",
            selected_C=best_c, C_candidates=[.25, 1, 4], max_iter=classifier.max_iter,
            iterations_completed=classifier.n_iter_.tolist(), class_weight="balanced", selection_split="validation")
    else:
        if not re.fullmatch(r"[a-f0-9]{40}", args.revision or ""):
            raise ValueError("Transformer revision must be a pinned 40-character commit SHA")
        if args.preprocessing == "vncorenlp" and not args.segmenter_path:
            raise ValueError("vncorenlp preprocessing requires --segmenter-path")
        import numpy as np
        import torch
        from datasets import Dataset
        from transformers import AutoTokenizer, AutoModelForSequenceClassification, Trainer, TrainingArguments, DataCollatorWithPadding, set_seed
        set_seed(args.seed)
        segmenter = None
        if args.preprocessing == "vncorenlp":
            segmenter = load_segmenter(args.segmenter_path)
        tokenizer = AutoTokenizer.from_pretrained(args.model, revision=args.revision)
        model = AutoModelForSequenceClassification.from_pretrained(args.model, revision=args.revision, num_labels=len(labels),
            id2label=dict(enumerate(labels)), label2id={label: i for i, label in enumerate(labels)}, ignore_mismatched_sizes=True)
        def dataset(texts, targets):
            prepared = [" ".join(segmenter.word_segment(t)) for t in texts] if segmenter else texts
            encoded = tokenizer(prepared, truncation=True, max_length=args.max_length)
            return Dataset.from_dict(dict(encoded, labels=[labels.index(label) for label in targets]))
        val_ds = dataset(vx, vy)
        training_args = TrainingArguments(**transformer_training_arguments(args, out, torch.cuda.is_available()))
        weights = training_class_weights(y, args.class_weight, labels)
        class WeightedTrainer(Trainer):
            def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
                outputs = model(**inputs)
                loss = weighted_classification_loss(outputs.logits, inputs["labels"], weights)
                return (loss, outputs) if return_outputs else loss
        trainer_class = WeightedTrainer if args.class_weight != "none" else Trainer
        trainer = trainer_class(model=model, args=training_args,
            train_dataset=dataset(x, y), eval_dataset=val_ds, data_collator=DataCollatorWithPadding(tokenizer),
            processing_class=tokenizer,
            compute_metrics=lambda p: {"macro_f1": metrics([labels[i] for i in p.label_ids], [labels[i] for i in np.argmax(p.predictions, axis=1)], labels)["macro_f1"]})
        if args.class_weight != "none":
            trainer.model_accepts_loss_kwargs = False
        trainer.train(); trainer.save_model(str(out)); tokenizer.save_pretrained(out)
        predictions = [labels[i] for i in np.argmax(trainer.predict(val_ds).predictions, axis=1)]
        report = metrics(vy, predictions, labels)
        (out / "training_history.json").write_text(json.dumps(trainer.state.log_history, indent=2), encoding="utf-8")
        report["trainable_parameters"] = sum(p.numel() for p in model.parameters() if p.requires_grad)
        report["peak_vram_bytes"] = torch.cuda.max_memory_allocated() if torch.cuda.is_available() else None
        architecture = architecture_metadata(model)
        actual_training = dict(learning_rate=training_args.learning_rate, epochs_requested=training_args.num_train_epochs,
            epochs_completed=trainer.state.epoch, global_step=trainer.state.global_step,
            best_checkpoint=trainer.state.best_model_checkpoint, best_validation_macro_f1=trainer.state.best_metric,
            batch_size=training_args.per_device_train_batch_size,
            effective_batch_size=training_args.per_device_train_batch_size * training_args.gradient_accumulation_steps * training_args.world_size,
            gradient_accumulation_steps=training_args.gradient_accumulation_steps, world_size=training_args.world_size,
            max_length=args.max_length, optimizer=str(training_args.optim.value), weight_decay=training_args.weight_decay,
            scheduler=str(training_args.lr_scheduler_type.value), warmup_steps=training_args.warmup_steps,
            fp16=training_args.fp16, device=str(training_args.device), selection_split="validation")
        actual_training.update(class_weight_policy=args.class_weight,
            class_weights=dict(zip(labels, weights)), class_weight_fit_split="train",
            loss_objective="mean(weight_y * cross_entropy)" if args.class_weight != "none" else "cross_entropy")
        (out / "training_arguments.json").write_text(training_args.to_json_string(), encoding="utf-8")
        (out / "model_config.json").write_text(model.config.to_json_string(), encoding="utf-8")
    # Validation error export contains IDs/tags, not private review text.
    report["errors"] = [dict(id=row["id"], expected=row["label"], predicted=str(predicted), tags=row.get("tags", []))
                        for row, predicted in zip(val, predictions) if row["label"] != predicted]
    report["elapsed_seconds"] = time.perf_counter() - started
    (out / "validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    import hashlib
    data_fingerprint = fingerprint(args.data)
    dataset_id = hashlib.sha256(json.dumps(data_fingerprint, sort_keys=True).encode()).hexdigest()[:12]
    model_id = args.model.split('/')[-1] if args.backend == 'transformers' else 'tfidf-lr'
    hyperparameters = {key: getattr(args, key) for key in ("backend", "preprocessing", "epochs", "learning_rate",
        "weight_decay", "class_weight", "max_length", "batch_size", "gradient_accumulation_steps")}
    training_id = hashlib.sha256(json.dumps(hyperparameters, sort_keys=True).encode()).hexdigest()[:12]
    version = f"{model_id}:{(args.revision or 'local')[:12]}:s{args.seed}:d{dataset_id}:t{training_id}"
    requested = vars(args).copy()
    metadata = dict(requested, model_version=version, data_sha256=data_fingerprint, python=platform.python_version(),
                    preprocessing="NFC-whitespace-v1", evaluation="validation only; run evaluate_sentiment for final test")
    metadata.update(schema_version=2, architecture=architecture, training=actual_training,
                    requested_arguments=requested, train_count=len(train), validation_count=len(val))
    if args.backend == "sklearn":
        metadata.update(model="tfidf-logistic-regression", revision=None, epochs=None, learning_rate=None,
                        batch_size=None, gradient_accumulation_steps=None, max_length=None, segmenter_path=None)
    metadata["text_preprocessing"] = args.preprocessing if args.backend == "transformers" else "normalize"
    metadata["labels"] = labels
    metadata['supervision']=supervision
    descriptor=Path(args.data)/'task.json'
    if descriptor.is_file():
        metadata['task_spec']=json.loads(descriptor.read_text(encoding='utf-8'))
    metadata["code_commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    code_files = sorted(Path(__file__).parent.glob("*.py"))
    metadata["pipeline_sha256"] = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in code_files}
    metadata["code_has_local_changes"] = bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip())
    if args.segmenter_path:
        metadata["segmenter_path"] = str(Path(args.segmenter_path).resolve())
        segmenter_files = ["VnCoreNLP-1.2.jar", "models/wordsegmenter/vi-vocab", "models/wordsegmenter/wordsegmenter.rdr"]
        metadata["segmenter_sha256"] = {name: hashlib.sha256((Path(args.segmenter_path)/name).read_bytes()).hexdigest()
                                       for name in segmenter_files}
    (out / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (out / "environment.txt").write_text(subprocess.check_output([__import__('sys').executable, "-m", "pip", "freeze"], text=True), encoding="utf-8")


if __name__ == "__main__":
    main()
