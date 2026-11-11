"""Measure actual tokenizer lengths after each model's preprocessing, without training."""
import argparse
import json
import math
from pathlib import Path
import statistics

from ml.benchmark import read_config
from ml.data import read_jsonl, fingerprint
from ml.text import normalize_text
from ml.train_sentiment import load_segmenter


def length_statistics(lengths, maximum):
    ordered = sorted(lengths)
    return dict(count=len(lengths), median=statistics.median(lengths) if lengths else 0,
        p95=ordered[max(0, math.ceil(len(ordered)*.95)-1)] if ordered else 0,
        maximum=max(lengths, default=0), over_max_length=sum(n > maximum for n in lengths),
        truncation_rate=sum(n > maximum for n in lengths)/len(lengths) if lengths else None)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--data", required=True)
    parser.add_argument("--segmenter-path", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    from transformers import AutoTokenizer
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    config = read_config(args.config)
    original = {split: [normalize_text(r["text"]) for r in read_jsonl(Path(args.data)/f"{split}.jsonl")]
                for split in ("train", "validation", "test")}
    models = [m for m in config["models"] if m.get("backend") != "sklearn"]
    report = dict(stage="distribution-only-not-final-model-test", data_sha256=fingerprint(args.data),
        max_length_fixed=config["training"]["max_length"], note="Special tokens included; no parameters selected from test statistics.", models=[])
    segmenter = None
    fig, axes = plt.subplots(len(models), 1, figsize=(8, 1.6*len(models)), squeeze=False)
    for index, model in enumerate(models):
        if model["preprocessing"] == "vncorenlp" and segmenter is None:
            segmenter = load_segmenter(args.segmenter_path)
        tokenizer = AutoTokenizer.from_pretrained(model["checkpoint"], revision=model["revision"], trust_remote_code=False)
        row = dict(model=model["id"], revision=model["revision"], preprocessing=model["preprocessing"], splits={})
        for split, texts in original.items():
            prepared = [" ".join(segmenter.word_segment(t)) for t in texts] if model["preprocessing"] == "vncorenlp" else texts
            encoded = tokenizer(prepared, truncation=False, add_special_tokens=True)
            lengths = [len(ids) for ids in encoded["input_ids"]]
            row["splits"][split] = length_statistics(lengths, config["training"]["max_length"])
            axes[index,0].hist(lengths, bins=25, alpha=.5, label=split)
        axes[index,0].axvline(config["training"]["max_length"], color="red", linestyle="--", label="fixed max length")
        axes[index,0].set_title(model["id"], fontsize=10); axes[index,0].set_ylabel("Samples", fontsize=9)
        axes[index,0].tick_params(labelsize=9)
        report["models"].append(row)
    handles, labels = axes[0,0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4, fontsize=9)
    axes[-1,0].set_xlabel("Tokens including special tokens after model-specific preprocessing")
    fig.tight_layout(rect=(0,0,1,.97))
    out = Path(args.output); out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out/"token-lengths.png", dpi=150); plt.close(fig)
    (out/"tokenization-audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"models":len(models),"stage":report["stage"]}))


if __name__ == "__main__":
    main()
