"""Review gates and group-disjoint splits. No automatic star-to-text labels."""
import argparse
import hashlib
import json
import random
from difflib import SequenceMatcher
from pathlib import Path
from app.ai_text import normalize_text


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def reviewed(rows):
    for row in rows:
        if row.get("review_status") != "approved" or not row.get("reviewer") or not row.get("license") or not row.get("source") or not row.get("group_id"):
            raise ValueError(f"{row.get('id')}: requires reviewer, approval, provenance, license and group_id")
        if "text" in row and row.get("label") not in {"positive", "neutral", "negative"}:
            raise ValueError(f"{row.get('id')}: missing human sentiment label")
    return rows


def text_of(row):
    return normalize_text(row.get("text", row.get("question", ""))).lower()


def grouped_split(rows, seed=42):
    """Merge both curator groups and near duplicates before assigning whole groups."""
    reviewed(rows)
    parent = list(range(len(rows)))
    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    normalized = [text_of(r) for r in rows]
    for i in range(len(rows)):
        for j in range(i):
            if rows[i]["group_id"] == rows[j]["group_id"] or SequenceMatcher(None, normalized[i], normalized[j]).ratio() >= 0.88:
                parent[root(i)] = root(j)
    groups = {}
    for i, row in enumerate(rows):
        groups.setdefault(root(i), []).append(row)
    values = list(groups.values())
    if len(values) < 7:
        raise ValueError("Need at least 7 independent groups; expand reviewed data")
    random.Random(seed).shuffle(values)
    # Approximate 70/15/15 by groups; do not split a large duplicate family to hit exact ratios.
    n = len(values)
    a, b = max(1, int(n*.7)), max(2, int(n*.85))
    parts = {"train": values[:a], "validation": values[a:b], "test": values[b:]}
    return {name: [row for group in grouped for row in group] for name, grouped in parts.items()}


def load_splits(directory):
    splits = {name: reviewed(read_jsonl(Path(directory) / f"{name}.jsonl")) for name in ("train", "validation", "test")}
    for left, right in (("train", "validation"), ("train", "test"), ("validation", "test")):
        if {r["group_id"] for r in splits[left]} & {r["group_id"] for r in splits[right]}:
            raise ValueError("Leaking group across splits")
        for a in splits[left]:
            if any(SequenceMatcher(None, text_of(a), text_of(b)).ratio() >= .88 for b in splits[right]):
                raise ValueError("Near-duplicate leakage across splits")
    if not all(splits.values()):
        raise ValueError("Every split must be nonempty")
    return splits


def fingerprint(directory):
    return {name: hashlib.sha256((Path(directory) / f"{name}.jsonl").read_bytes()).hexdigest() for name in ("train", "validation", "test")}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("input"); p.add_argument("output"); p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()
    for name, rows in grouped_split(read_jsonl(args.input), args.seed).items():
        write_jsonl(Path(args.output) / f"{name}.jsonl", rows)
    load_splits(args.output)
    Path(args.output, "split_manifest.json").write_text(json.dumps({"seed": args.seed, "sha256": fingerprint(args.output)}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
