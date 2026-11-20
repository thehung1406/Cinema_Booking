"""Verify and restore the tracked KB snapshot without credentials or a running DB."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "pipelines/knowledge/snapshot"


def contained(root, relative):
    path = PurePosixPath(relative)
    if (not relative or path.is_absolute() or ".." in path.parts
            or "\\" in relative or ":" in relative or path == PurePosixPath(".")):
        raise ValueError(f"Invalid snapshot path: {relative}")
    target = (root / relative).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError(f"Path leaves snapshot or destination: {relative}")
    return target


def restore(snapshot, destination, *, check=False, overwrite=False):
    snapshot, destination = Path(snapshot).resolve(), Path(destination).resolve()
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    if manifest["version"] != 1 or not manifest["files"]:
        raise ValueError("Unsupported or empty knowledge snapshot")
    pending, seen = [], set()
    # Check the whole package and all conflicts before writing any files.
    for entry in manifest["files"]:
        relative = entry["path"]
        source = contained(snapshot, relative)
        target = contained(destination, relative)
        if target in seen:
            raise ValueError(f"Duplicate snapshot destination: {relative}")
        seen.add(target)
        data = source.read_bytes()
        if len(data) != entry["bytes"] or hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise ValueError(f"Snapshot checksum mismatch: {relative}")
        if not check:
            if target.exists() and target.read_bytes() == data:
                continue
            if target.exists() and not overwrite:
                raise ValueError(f"Existing file differs: {relative}. Review it before using --overwrite.")
            for parent in target.parents:
                if parent.exists() and not parent.is_dir():
                    raise ValueError(f"Destination parent is not a directory: {parent}")
            pending.append((target, data))
    for target, data in pending:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return {"verified_files": len(seen), "written_files": len(pending), "check_only": check}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / ".local/knowledge")
    parser.add_argument("--check", action="store_true", help="Verify tracked files only; write nothing")
    parser.add_argument("--overwrite", action="store_true", help="Replace differing local KB files after review")
    args = parser.parse_args()
    if args.check and args.overwrite:
        parser.error("--check and --overwrite cannot be combined")
    try:
        print(json.dumps(restore(SNAPSHOT, args.output, check=args.check, overwrite=args.overwrite)))
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, f"Knowledge restore failed: {error}\n")


if __name__ == "__main__":
    main()
