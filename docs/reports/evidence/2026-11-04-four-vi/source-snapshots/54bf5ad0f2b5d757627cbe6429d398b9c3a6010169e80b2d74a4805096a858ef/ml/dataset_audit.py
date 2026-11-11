"""Dataset admission/EDA from real records; never fabricate labels or reviewers."""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import statistics

from ml.data import read_jsonl, reviewed, text_of
from ml.task_spec import label_order

LABELS = ("negative", "neutral", "positive")


def audit(directory):
    directory = Path(directory)
    labels_order=label_order(directory)
    result = {"dataset": directory.name, "splits": {}, "problems": [], "sha256": {}}
    locations, groups, identifiers = {}, {}, {}
    for split in ("train", "validation", "test"):
        path = directory / f"{split}.jsonl"
        if not path.is_file():
            result["problems"].append(f"Missing {split}.jsonl")
            continue
        rows = read_jsonl(path)
        result["sha256"][split] = hashlib.sha256(path.read_bytes()).hexdigest()
        try:
            reviewed(rows)
        except ValueError as exc:
            result["problems"].append(str(exc))
        labels = Counter(row.get("label") for row in rows)
        lengths = [len(str(row.get("text", ""))) for row in rows]
        words = [len(str(row.get("text", "")).split()) for row in rows]
        duplicates = 0
        for row in rows:
            identifier = str(row.get("id", ""))
            if not identifier or identifier in identifiers:
                result["problems"].append(f"Missing/duplicate sample ID in {split}")
            identifiers[identifier] = split
            normalized = text_of(row)
            digest = hashlib.sha256(normalized.encode()).hexdigest()
            if not normalized:
                result["problems"].append(f"Empty text in {split}: {identifier}")
            if digest in locations:
                duplicates += 1
                if locations[digest] != split:
                    result["problems"].append(f"Exact text leakage: {locations[digest]} -> {split}")
            locations[digest] = split
            group = str(row.get("group_id", ""))
            if group in groups and groups[group] != split:
                result["problems"].append(f"Group leakage: {group}")
            groups[group] = split
        result["splits"][split] = {
            "count": len(rows), "labels": dict(labels), "exact_duplicates": duplicates,
            "characters": {"min": min(lengths, default=0), "max": max(lengths, default=0),
                           "median": statistics.median(lengths) if lengths else 0},
            "words": {"median": statistics.median(words) if words else 0},
            "lengths_characters": lengths, "lengths_words": words,
            "sources": dict(Counter(row.get("source", "unknown") for row in rows)),
            "synthetic_count": sum(bool(row.get("synthetic")) for row in rows),
        }
        if set(labels) != set(labels_order):
            result["problems"].append(f"{split} must contain every declared sentiment label")
        if any(row.get("synthetic") for row in rows):
            result["problems"].append(f"Synthetic records in {split}; not admissible as independent benchmark")
    result["problems"] = sorted(set(result["problems"]))
    result["admissible"] = not result["problems"]
    result['label_order']=list(labels_order)
    result["limitations"] = ["Exact/group leakage checked; near duplicates and provenance require curator review."]
    return result


def write_report(report, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    labels_order=report.get('label_order',LABELS)
    fig, axes = plt.subplots(1, 2, figsize=(8.5, 3.2))
    for index, (name, stats) in enumerate(report["splits"].items()):
        axes[0].bar([x + index*.25 for x in range(len(labels_order))],
                    [stats["labels"].get(label, 0) for label in labels_order], width=.25, label=name)
        axes[1].hist(stats["lengths_characters"], bins=30, alpha=.45, label=name)
    axes[0].set_xticks([x+.25 for x in range(len(labels_order))], labels_order)
    axes[0].set_ylabel("Samples")
    axes[1].set_xlabel("Characters per sample")
    for axis in axes:
        axis.tick_params(labelsize=10)
        axis.legend(fontsize=9)
    fig.suptitle(f"{report['dataset']} — observed distribution")
    fig.tight_layout()
    fig.savefig(output / "distribution.png", dpi=160)
    plt.close(fig)
    rows = [f"# Data card: {report['dataset']}", "", f"Admissible: {report['admissible']}", "",
            "| Split | Samples | Negative | Neutral | Positive | Median characters |",
            "| --- | --- | --- | --- | --- | --- |"]
    for name, stats in report["splits"].items():
        values = [name, stats["count"], *(stats["labels"].get(label, 0) for label in LABELS), stats["characters"]["median"]]
        rows.append("| " + " | ".join(map(str, values)) + " |")
    rows += ["", "## Issues requiring review", *[f"- {p}" for p in report["problems"] + report["limitations"]]]
    (output / "DATA_CARD.md").write_text("\n".join(rows) + "\n", encoding="utf-8")


def export_annotation(input_path, output_path):
    """No guessed labels: a person supplies label/reviewer/approval later."""
    with Path(output_path).open("w", encoding="utf-8-sig", newline="") as stream:
        fields = ["id", "text", "label", "reviewer", "second_label", "second_reviewer", "review_status", "group_id", "source", "license", "annotation_note"]
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in read_jsonl(input_path):
            writer.writerow({key: row.get(key, "") for key in fields} | {"label": "", "reviewer": "", "review_status": "pending"})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = audit(args.directory)
    write_report(report, args.output)
    print(json.dumps({"admissible": report["admissible"], "problems": report["problems"]}, ensure_ascii=False))
    if not report["admissible"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
