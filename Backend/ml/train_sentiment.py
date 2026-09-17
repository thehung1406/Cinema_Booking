"""Train TF-IDF/LR or segmented PhoBERT; test data is never used for selection."""
import argparse
import json
import platform
import subprocess
from pathlib import Path
from app.ai_text import normalize_text
from ml.data import load_splits, fingerprint

LABELS = ["negative", "neutral", "positive"]


def metrics(y, predictions):
    from sklearn.metrics import classification_report, confusion_matrix, f1_score
    return {"macro_f1": f1_score(y, predictions, labels=LABELS, average="macro", zero_division=0),
            "per_class": classification_report(y, predictions, labels=LABELS, output_dict=True, zero_division=0),
            "confusion_matrix": confusion_matrix(y, predictions, labels=LABELS).tolist(), "label_order": LABELS}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True); p.add_argument("--output", required=True)
    p.add_argument("--backend", choices=["sklearn", "transformers"], default="sklearn")
    p.add_argument("--model", default="vinai/phobert-base")
    p.add_argument("--revision", help="Pin a Hugging Face commit SHA for reproducible downloads")
    p.add_argument("--segmenter-path"); p.add_argument("--seed", type=int, default=42)
    p.add_argument("--epochs", type=int, default=3)
    args = p.parse_args()
    splits = load_splits(args.data)
    for name, rows in splits.items():
        if {r['label'] for r in rows} != set(LABELS):
            raise ValueError(f"{name} must include every class; collect additional independent groups")
    out = Path(args.output); out.mkdir(parents=True, exist_ok=False)
    train, val = splits["train"], splits["validation"]
    x, vx = [normalize_text(r["text"]) for r in train], [normalize_text(r["text"]) for r in val]
    y, vy = [r["label"] for r in train], [r["label"] for r in val]
    if args.backend == "sklearn":
        import joblib
        from sklearn.pipeline import Pipeline
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        candidates = []
        for c in (.25, 1, 4):
            model = Pipeline([("tfidf", TfidfVectorizer(analyzer="char", ngram_range=(2, 5), min_df=1)),
                              ("classifier", LogisticRegression(C=c, max_iter=1000, class_weight="balanced", random_state=args.seed))])
            model.fit(x, y)
            report = metrics(vy, model.predict(vx))
            candidates.append((report["macro_f1"], c, model, report))
        _, best_c, model, report = max(candidates, key=lambda item: item[0])
        report["selected_C"] = best_c
        joblib.dump(model, out / "model.joblib")
    else:
        if not args.segmenter_path or not args.revision:
            raise ValueError("PhoBERT requires --segmenter-path and --revision; use identical segmentation at inference")
        import numpy as np
        import py_vncorenlp
        from datasets import Dataset
        from transformers import AutoTokenizer, AutoModelForSequenceClassification, Trainer, TrainingArguments, DataCollatorWithPadding, set_seed
        set_seed(args.seed)
        segmenter = py_vncorenlp.VnCoreNLP(save_dir=str(Path(args.segmenter_path).resolve()), annotators=["wseg"])
        tokenizer = AutoTokenizer.from_pretrained(args.model, revision=args.revision)
        model = AutoModelForSequenceClassification.from_pretrained(args.model, revision=args.revision, num_labels=3,
            id2label=dict(enumerate(LABELS)), label2id={label: i for i, label in enumerate(LABELS)})
        def dataset(texts, labels):
            encoded = tokenizer([" ".join(segmenter.word_segment(t)) for t in texts], truncation=True, max_length=256)
            return Dataset.from_dict(dict(encoded, labels=[LABELS.index(label) for label in labels]))
        val_ds = dataset(vx, vy)
        trainer = Trainer(model=model, args=TrainingArguments(output_dir=str(out / "checkpoints"),
            seed=args.seed, num_train_epochs=args.epochs, per_device_train_batch_size=8, per_device_eval_batch_size=8,
            learning_rate=2e-5, eval_strategy="epoch", save_strategy="epoch", load_best_model_at_end=True,
            metric_for_best_model="macro_f1", greater_is_better=True, save_total_limit=1, report_to=[]),
            train_dataset=dataset(x, y), eval_dataset=val_ds, data_collator=DataCollatorWithPadding(tokenizer),
            compute_metrics=lambda p: {"macro_f1": metrics([LABELS[i] for i in p.label_ids], [LABELS[i] for i in np.argmax(p.predictions, axis=1)])["macro_f1"]})
        trainer.train(); trainer.save_model(str(out)); tokenizer.save_pretrained(out)
        report = metrics(vy, [LABELS[i] for i in np.argmax(trainer.predict(val_ds).predictions, axis=1)])
    (out / "validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    metadata = dict(vars(args), model_version=out.name, data_sha256=fingerprint(args.data), python=platform.python_version(),
                    preprocessing="NFC-whitespace-v1", evaluation="validation only; run evaluate_sentiment for final test")
    if args.segmenter_path:
        metadata["segmenter_path"] = str(Path(args.segmenter_path).resolve())
    (out / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (out / "environment.txt").write_text(subprocess.check_output([__import__('sys').executable, "-m", "pip", "freeze"], text=True), encoding="utf-8")


if __name__ == "__main__":
    main()
