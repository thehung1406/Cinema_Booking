"""Check download integrity without loading pickle or requiring large model files."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location(
    "check_sentiment_models", Path(__file__).resolve().parents[2] / "scripts/ai/check_sentiment_models.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SharedSentimentModelTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.entries = []
        for name, (backend, files) in MODULE.REQUIRED.items():
            (self.root / name).mkdir()
            for filename in files:
                data = b"synthetic model bytes"
                if filename == "metadata.json":
                    data = json.dumps(dict(backend=backend, labels=["negative", "neutral", "positive"],
                        production_promoted=False, model_version=f"{name}:test")).encode()
                path = self.root / name / filename
                path.write_bytes(data)
                self.entries.append(dict(path=f"{name}/{filename}", bytes=len(data),
                    sha256=hashlib.sha256(data).hexdigest()))
        self.write_manifest()

    def write_manifest(self):
        (self.root / "manifest.json").write_text(
            json.dumps(dict(schema_version=1, files=self.entries)), encoding="utf-8")

    def test_complete_package_verifies_without_loading_models(self):
        self.assertEqual(MODULE.verify(self.root)["verified_files"], 9)

    def test_lfs_pointer_has_actionable_download_error(self):
        (self.root / "lr/model.joblib").write_bytes(b"version https://git-lfs.github.com/spec/v1\n")
        with self.assertRaisesRegex(ValueError, "git lfs pull"):
            MODULE.verify(self.root)

    def test_corrupted_download_is_rejected(self):
        (self.root / "visobert/model.safetensors").write_bytes(b"truncated")
        with self.assertRaisesRegex(ValueError, "Checksum mismatch"):
            MODULE.verify(self.root)

    def test_missing_file_is_rejected(self):
        (self.root / "visobert/tokenizer.json").unlink()
        with self.assertRaises(FileNotFoundError):
            MODULE.verify(self.root)

    def test_manifest_cannot_hide_required_files_or_read_outside_directory(self):
        for relative in ("../outside", self.entries[1]["path"]):
            with self.subTest(relative=relative):
                self.entries[0]["path"] = relative
                self.write_manifest()
                with self.assertRaisesRegex(ValueError, "required inference files"):
                    MODULE.verify(self.root)


if __name__ == "__main__":
    unittest.main()
