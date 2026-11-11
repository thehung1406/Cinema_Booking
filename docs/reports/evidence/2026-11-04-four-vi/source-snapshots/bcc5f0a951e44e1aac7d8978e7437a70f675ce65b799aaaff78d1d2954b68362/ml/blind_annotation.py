"""Independent human passes and pre-adjudication agreement; no guessed gold labels."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import random

from ml.data import read_jsonl, write_jsonl

LABELS = ("negative", "neutral", "positive")
VISIBLE_FIELDS = ("id", "text", "source", "license", "group_id", "synthetic")


def prepare(original, output, per_label=200, seed=20261104):
    output = Path(output)
    if output.exists():
        raise ValueError("Choose a new output directory; never overwrite human work")
    if per_label < 1:
        raise ValueError("Positive sample size required")
    candidates, seen = defaultdict(lambda: defaultdict(list)), set()
    for row in read_jsonl(original):
        if row.get("synthetic") or row.get("suggested_label") not in LABELS:
            continue
        text = " ".join(row["text"].casefold().split())
        digest = hashlib.sha256(text.encode()).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        candidates[row["suggested_label"]][row.get("platform", "unknown")].append(row)
    rng, selected, strata = random.Random(seed), [], []
    for label in LABELS:
        buckets = candidates[label]
        if sum(map(len, buckets.values())) < per_label:
            raise ValueError(f"Not enough distinct candidates in suggested stratum {label}")
        for rows in buckets.values():
            rng.shuffle(rows)
        chosen = []
        while len(chosen) < per_label:
            for platform in sorted(buckets):
                if buckets[platform] and len(chosen) < per_label:
                    chosen.append(buckets[platform].pop())
        selected.extend(chosen)
        strata.append(dict(suggested_label=label, selected=len(chosen),
            platforms=dict(Counter(r.get("platform", "unknown") for r in chosen))))
    # Only source/text fields enter human interfaces; neither publisher hints nor
    # any prior annotation decisions are copied into either independent pass.
    blinded = [{key: row.get(key) for key in VISIBLE_FIELDS} | dict(label=None, reviewer=None,
        review_status="pending", annotation_origin="blind-human-annotation-pending") for row in selected]
    output.mkdir(parents=True)
    for name, order_seed in (("A", seed + 1), ("B", seed + 2)):
        ordered = blinded.copy()
        random.Random(order_seed).shuffle(ordered)
        write_jsonl(output / f"pass-{name}-pending.jsonl", ordered)
    manifest = dict(source_sha256=hashlib.sha256(Path(original).read_bytes()).hexdigest(),
        sample_seed=seed, count=len(blinded), per_suggested_label=per_label, strata=strata,
        human_approved_count=0, intended_use="Double-annotation development batch, not a natural-distribution test set",
        sampling="Round-robin platforms within publisher-suggested strata, exact casefolded text deduplicated",
        caveats=["Publisher labels used for sampling only, never accepted as gold", "No author/film IDs in source: no film-disjoint claim", "Near duplicates still require grouping before train/test", "Same 600 texts in two orders; not two datasets"])
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def reconcile(first, second):
    def index(path):
        rows = read_jsonl(path)
        if len({str(r["id"]) for r in rows}) != len(rows):
            raise ValueError("Duplicate annotation IDs")
        return {str(row["id"]): row for row in rows}
    a, b = index(first), index(second)
    if a.keys() != b.keys():
        raise ValueError("Independent passes must cover the same sample IDs")
    pairs, agreed, conflicts, pending = [], [], [], []
    for identifier in sorted(a):
        left, right = a[identifier], b[identifier]
        if any(r.get('annotation_mode')=='ai-assisted' or r.get('suggestion_origin')=='ai-ollama' for r in (left,right)):
            raise ValueError('AI-assisted decisions cannot be presented as blind independent annotation')
        if any(left.get(key) != right.get(key) for key in VISIBLE_FIELDS):
            raise ValueError("Source/text/group changed across passes")
        if left.get("synthetic"):
            raise ValueError("Synthetic reviews cannot enter the real-film batch")
        complete = lambda r: (r.get("label") in LABELS and r.get("review_status") == "approved"
            and bool(str(r.get("reviewer") or "").strip())
            and r.get("annotation_origin") == "manual-tool-confirmation")
        if not complete(left) or not complete(right):
            pending.append(identifier)
            continue
        if left["reviewer"].strip().casefold() == right["reviewer"].strip().casefold():
            raise ValueError("Two independent people required; a repeated reviewer is not double annotation")
        pairs.append((left["label"], right["label"]))
        merged = {key: left.get(key) for key in VISIBLE_FIELDS} | dict(
            first_label=left["label"], second_label=right["label"], first_reviewer=left["reviewer"],
            second_reviewer=right["reviewer"], first_note=left.get("annotation_note", ""),
            second_note=right.get("annotation_note", ""))
        if left["label"] == right["label"]:
            agreed.append(merged | dict(label=left["label"], reviewer=left["reviewer"],
                review_status="approved", annotation_origin="independent-human-agreement"))
        else:
            conflicts.append(merged | dict(label=None, reviewer=None, review_status="pending",
                annotation_origin="needs-human-adjudication"))
    count = len(pairs)
    observed = sum(x == y for x, y in pairs) / count if count else None
    marginals_a, marginals_b = Counter(x for x, _ in pairs), Counter(y for _, y in pairs)
    expected = sum(marginals_a[label]*marginals_b[label] for label in LABELS)/count**2 if count else None
    kappa = (observed-expected)/(1-expected) if count and expected < 1 else None
    report = dict(stage="pre-adjudication-human-agreement", total=len(a), double_confirmed=count,
        pending=len(pending), agreed=len(agreed), disagreements=len(conflicts), raw_agreement=observed,
        cohen_kappa=kappa, kappa_undefined_reason="No paired decisions or constant identical marginals" if kappa is None else None,
        marginal_labels_A=dict(marginals_a), marginal_labels_B=dict(marginals_b),
        pending_ids=pending, disagreement_ids=[row["id"] for row in conflicts],
        note="Agreement applies only to double-confirmed rows before adjudication; no human decision is generated.")
    return report, agreed, conflicts


def accept_adjudications(conflicts, path):
    """Keep explicit third-person decisions; unanswered conflicts remain unresolved."""
    originals = {str(row['id']): row for row in conflicts}
    decisions = read_jsonl(path)
    if len({str(row['id']) for row in decisions}) != len(decisions):
        raise ValueError('Duplicate adjudication IDs')
    accepted = []
    for row in decisions:
        original = originals.get(str(row['id']))
        if original is None or any(row.get(key) != original.get(key) for key in (*VISIBLE_FIELDS,
                'first_label','second_label','first_reviewer','second_reviewer')):
            raise ValueError('Adjudication source or independent decisions changed')
        if row.get('review_status') != 'approved':
            continue
        reviewer = str(row.get('reviewer') or '').strip().casefold()
        if (row.get('annotation_origin') != 'manual-adjudication' or row.get('label') not in LABELS
                or not reviewer or reviewer in {str(original[k]).strip().casefold() for k in ('first_reviewer','second_reviewer')}
                or not str(row.get('annotation_note') or '').strip()):
            raise ValueError('A distinct third reviewer and an explicit reason are required')
        accepted.append(row)
    return accepted


def main():
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=["prepare", "reconcile"])
    p.add_argument("--input", required=True)
    p.add_argument("--second")
    p.add_argument("--output", required=True)
    p.add_argument("--per-label", type=int, default=200)
    p.add_argument("--adjudicated")
    args = p.parse_args()
    if args.action == "prepare":
        result = prepare(args.input, args.output, args.per_label)
    else:
        if not args.second:
            p.error("--second required")
        destination = Path(args.output)
        if destination.exists():
            raise ValueError("Choose a new reconciliation snapshot directory")
        result, agreed, conflicts = reconcile(args.input, args.second)
        adjudicated = accept_adjudications(conflicts, args.adjudicated) if args.adjudicated else []
        result.update(adjudicated=len(adjudicated), accepted=len(agreed)+len(adjudicated),
            unresolved_disagreements=len(conflicts)-len(adjudicated),
            batch_complete=result['pending'] == 0 and len(conflicts) == len(adjudicated))
        destination.mkdir(parents=True)
        write_jsonl(destination / "agreed.jsonl", agreed)
        write_jsonl(destination / "accepted.jsonl", agreed + adjudicated)
        write_jsonl(destination / "adjudication-pending.jsonl", conflicts)
        (destination / "agreement.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if not key.endswith("_ids")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
