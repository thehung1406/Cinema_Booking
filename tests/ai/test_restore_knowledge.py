"""Portable KB transfer must verify content and preserve local changes."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location(
    "restore_knowledge", Path(__file__).resolve().parents[2] / "scripts/ai/restore_knowledge.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RestoreKnowledgeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.snapshot, self.output = self.root / "snapshot", self.root / "output"
        self.snapshot.mkdir()
        self.entries = []
        for name in ("guide.json", "raw/book.pdf"):
            data = name.encode()
            source = self.snapshot / name
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(data)
            self.entries.append(dict(path=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
        self.write_manifest()

    def write_manifest(self):
        (self.snapshot / "manifest.json").write_text(
            json.dumps(dict(version=1, files=self.entries)), encoding="utf-8")

    def test_restore_is_idempotent_and_check_writes_nothing(self):
        MODULE.restore(self.snapshot, self.output, check=True)
        self.assertFalse(self.output.exists())
        self.assertEqual(MODULE.restore(self.snapshot, self.output)["written_files"], 2)
        self.assertEqual(MODULE.restore(self.snapshot, self.output)["written_files"], 0)
        self.assertEqual((self.output / "raw/book.pdf").read_bytes(), b"raw/book.pdf")

    def test_corrupt_package_is_rejected_before_any_write(self):
        (self.snapshot / "raw/book.pdf").write_bytes(b"corrupt")
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            MODULE.restore(self.snapshot, self.output)
        self.assertFalse(self.output.exists())

    def test_late_conflict_preserves_every_local_file(self):
        target = self.output / "raw/book.pdf"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"local work")
        with self.assertRaisesRegex(ValueError, "Existing file differs"):
            MODULE.restore(self.snapshot, self.output)
        self.assertFalse((self.output / "guide.json").exists())
        self.assertEqual(target.read_bytes(), b"local work")
        MODULE.restore(self.snapshot, self.output, overwrite=True)
        self.assertEqual(target.read_bytes(), b"raw/book.pdf")

    def test_path_traversal_is_rejected(self):
        for relative in ("../outside", "/outside", "C:/outside", "raw\\outside"):
            with self.subTest(relative=relative):
                self.entries[-1]["path"] = relative
                self.write_manifest()
                with self.assertRaisesRegex(ValueError, "Invalid snapshot path"):
                    MODULE.restore(self.snapshot, self.output)
                self.assertFalse(self.output.exists())

    def test_real_shared_snapshot(self):
        result = MODULE.restore(MODULE.SNAPSHOT, self.output)
        self.assertGreaterEqual(result["verified_files"], 8)
        for name in ("booking-guide.json", "film-book.json", "cinematography-summary.json"):
            documents = json.loads((self.output / name).read_text(encoding="utf-8"))
            self.assertTrue(documents)
            self.assertTrue(all(document["approved"] is False for document in documents))


if __name__ == "__main__":
    unittest.main()
