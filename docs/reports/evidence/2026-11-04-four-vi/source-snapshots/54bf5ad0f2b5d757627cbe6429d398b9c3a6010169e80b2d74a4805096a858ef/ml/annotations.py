"""Round-trip a human annotation worksheet; suggested labels are never promoted."""
import argparse
import csv
from pathlib import Path

from ml.data import read_jsonl, reviewed, write_jsonl
from ml.dataset_audit import export_annotation


def import_annotations(original_path, worksheet_path):
    originals = {str(row["id"]): row for row in read_jsonl(original_path)}
    result, seen = [], set()
    with Path(worksheet_path).open(encoding="utf-8-sig", newline="") as stream:
        for annotation in csv.DictReader(stream):
            identifier = annotation["id"]
            if identifier not in originals or identifier in seen:
                raise ValueError("Unknown or duplicate worksheet ID")
            seen.add(identifier)
            row = originals[identifier]
            if annotation["text"] != row["text"]:
                raise ValueError("Text changed; create a new source/version before annotation")
            approved = {key: annotation.get(key, "").strip() for key in
                        ("label", "reviewer", "review_status", "second_label", "second_reviewer", "annotation_note")}
            if approved["second_label"] and approved["second_label"] != approved["label"] and not approved["annotation_note"]:
                raise ValueError("Disagreement needs a recorded resolution")
            result.append(row | approved)
    if seen != set(originals):
        raise ValueError("Worksheet must cover every original sample")
    reviewed(result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["export", "import"])
    parser.add_argument("original")
    parser.add_argument("worksheet")
    parser.add_argument("--output")
    args = parser.parse_args()
    if args.action == "export":
        if Path(args.worksheet).exists():
            raise SystemExit("Refusing to overwrite an annotation worksheet")
        export_annotation(args.original, args.worksheet)
    else:
        if not args.output:
            parser.error("--output is required for import")
        write_jsonl(args.output, import_annotations(args.original, args.worksheet))


if __name__ == "__main__":
    main()
