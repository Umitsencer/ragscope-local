"""Exercise source integrity with synthetic bytes and no network access."""

import hashlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/fetch_pinned_sources.py"
spec = importlib.util.spec_from_file_location("fetch_pinned_sources", SCRIPT)
fetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)


class FetchTests(unittest.TestCase):
    def setUp(self):
        self.source = {"repository": "https://github.com/example/synthetic", "commit": "a" * 40}
        self.entry = {
            "path": "data/raw/synthetic/file.json",
            "source_path": "file.json",
            "sha256": hashlib.sha256(b"{}").hexdigest(),
        }

    def test_verified_download_and_existing_file_need_no_network(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(
                fetch.fetch_entry(
                    root, self.source, self.entry, True, lambda *a, **k: io.BytesIO(b"{}")
                ),
                "downloaded and verified",
            )
            self.assertEqual(fetch.fetch_entry(root, self.source, self.entry), "verified")

    def test_bad_hash_leaves_no_download(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                fetch.fetch_entry(
                    root, self.source, self.entry, True, lambda *a, **k: io.BytesIO(b"invalid")
                )
            self.assertEqual(list((root / "data/raw/synthetic").iterdir()), [])

    def test_path_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(ValueError):
            fetch.resolve_entry(Path(directory), self.source, {**self.entry, "path": "../escape"})

    def test_existing_mismatch_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / self.entry["path"]
            path.parent.mkdir(parents=True)
            path.write_bytes(b"original")
            with self.assertRaises(ValueError):
                fetch.fetch_entry(root, self.source, self.entry, True)
            self.assertEqual(path.read_bytes(), b"original")
