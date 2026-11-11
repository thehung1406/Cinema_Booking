"""Import the publisher's sentiment labels without inventing human annotation.

Official test remains intact. Exact/near matches to test are removed from train;
train/dev groups are formed before splitting. All removals are recorded by ID.
"""
import argparse
from collections import Counter
from difflib import SequenceMatcher
import hashlib
import json
from pathlib import Path
import random
import re

import httpx


def normalized(text):
    import unicodedata
    return " ".join(unicodedata.normalize("NFC", text).lower().split())


def near(left, right):
    if not left or not right or 2*min(len(left), len(right))/(len(left)+len(right)) < .88:
        return False
    matcher = SequenceMatcher(None, left, right)
    return matcher.quick_ratio() >= .88 and matcher.ratio() >= .88


def fetch(output, revision="4d1319fa229720d392c1dc0e323d10b40eeacbd0"):
    source = "undertheseanlp/UTS2017_Bank"
    if not re.fullmatch(r'[a-f0-9]{40}', revision):
        raise ValueError('Pin a 40-character publisher revision')
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        response = client.get(f"https://huggingface.co/api/datasets/{source}/revision/{revision}")
        response.raise_for_status()
        metadata = response.json()
        if metadata['sha'] != revision:
            raise ValueError('Publisher revision differs from the requested lock')
        if metadata.get("cardData", {}).get("license") != "apache-2.0":
            raise ValueError("Publisher license changed; review before importing")
        raw = {}
        for split in ("train", "test"):
            response = client.get(f"https://huggingface.co/datasets/{source}/resolve/{revision}/data/sentiment/{split}.jsonl")
            response.raise_for_status()
            raw[split] = [json.loads(line) for line in response.text.splitlines() if line.strip()]
    originals = {}
    for split, records in raw.items():
        originals[split] = []
        for index, row in enumerate(records):
            if row["sentiment"] not in {"positive", "neutral", "negative"}:
                raise ValueError("Unexpected publisher label")
            digest = hashlib.sha256(normalized(row["text"]).encode()).hexdigest()
            originals[split].append(dict(id=f"uts2017:{split}:{index}", text=row["text"], label=row["sentiment"],
                group_id=f"uts2017:{digest}", source=f"https://huggingface.co/datasets/{source}/tree/{revision}",
                license="Apache-2.0 (publisher dataset card)", review_status="approved",
                reviewer=f"external-publisher:{source}", annotation_origin="original-publisher-label",
                original_split=split, synthetic=False))
    test = originals["test"]
    test_texts = [normalized(row["text"]) for row in test]
    train, excluded = [], []
    for row in originals["train"]:
        text = normalized(row["text"])
        if any(near(text, candidate) for candidate in test_texts):
            excluded.append(row["id"])
        else:
            train.append(row)
    # Cluster train near-duplicate families. No family is split across train/dev.
    families = []
    for row in train:
        text = normalized(row["text"])
        matching = [i for i, group in enumerate(families) if any(near(text, normalized(r["text"])) for r in group)]
        if not matching:
            families.append([row])
        else:
            first = matching[0]
            families[first].append(row)
            for index in reversed(matching[1:]):
                families[first].extend(families.pop(index))
    for index, family in enumerate(families):
        for row in family:
            row["group_id"] = f"uts2017:train-family:{index}"
    random.Random(42).shuffle(families)
    # Allocate families by their label composition, reserving about 15% per label.
    target = {label: max(1, round(count*.15)) for label, count in Counter(r["label"] for r in train).items()}
    selected = Counter()
    parts = {"train": [], "validation": [], "test": test}
    for family in sorted(families, key=lambda group: sum(r["label"] == "neutral" for r in group), reverse=True):
        counts = Counter(row["label"] for row in family)
        into_dev = any(selected[label] < target[label] for label in counts)
        name = "validation" if into_dev else "train"
        parts[name].extend(family)
        if into_dev:
            selected.update(counts)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    for split, records in parts.items():
        (output/f"{split}.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False)+"\n" for row in records), encoding="utf-8")
    manifest = {"dataset": source, "revision": revision, "annotation_origin": "publisher; not group-member annotations",
        "license": metadata["cardData"]["license"], "test_preserved": True, "near_duplicate_threshold": .88,
        "excluded_training_ids_matching_test": excluded, "seed": 42,
        "splits": {split: {"count": len(rows), "labels": dict(Counter(r["label"] for r in rows))} for split, rows in parts.items()}}
    (output/"source_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="pipelines/ml/data/reviewed/uts2017-bank")
    parser.add_argument("--revision",default="4d1319fa229720d392c1dc0e323d10b40eeacbd0")
    args = parser.parse_args()
    if Path(args.output).exists():
        raise SystemExit("Output exists; choose a new version directory instead of overwriting annotations")
    fetch(args.output,args.revision)


if __name__ == "__main__":
    main()
