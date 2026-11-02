"""Deterministic ranking comparison on a frozen count snapshot (no personalisation)."""
import argparse
import json
from pathlib import Path
from math import sqrt


def wilson(positive, total):
    if not total: return 0
    p, z = positive/total, 1.96
    return (p + z*z/(2*total) - z*sqrt((p*(1-p)+z*z/(4*total))/total))/(1+z*z/total)


def compare(rows, minimum=10):
    for row in rows:
        if row["total"] < 0 or not 0 <= row["positive"] <= row["total"]:
            raise ValueError("Invalid frozen counts")
    eligible = [r for r in rows if r["total"] >= minimum]
    keys = {"positive_count": lambda r: r["positive"], "positive_ratio": lambda r: r["positive"]/r["total"], "wilson": lambda r: wilson(r["positive"], r["total"])}
    return {name: [dict(r, score=fn(r)) for r in sorted(eligible, key=lambda r: (-fn(r), str(r["film_id"])))] for name, fn in keys.items()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("input"); parser.add_argument("output"); parser.add_argument("--minimum", type=int, default=10)
    args = parser.parse_args()
    if args.minimum < 1: parser.error("minimum must be positive")
    rows = json.loads(Path(args.input).read_text(encoding="utf-8"))
    Path(args.output).write_text(json.dumps(compare(rows, args.minimum), ensure_ascii=False, indent=2), encoding="utf-8")
