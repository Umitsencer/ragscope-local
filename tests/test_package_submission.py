"""Synthetic release packaging tests; no network or model execution."""

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from package_submission import TOP_FILES, package, release_files


class PackagingTests(unittest.TestCase):
    def populate(self, root):
        for name in TOP_FILES:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}", encoding="utf-8")

    def test_excludes_local_assets_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.populate(root)
            for name in (
                "data/raw/private.json",
                "data/local_cache/vector.jsonl",
                ".venv/code.py",
                "chat.md",
                ".env",
            ):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("synthetic excluded fixture", encoding="utf-8")
            output = root / "dist/test.zip"
            result = package(root, output)
            self.assertEqual(result["file_count"], len(TOP_FILES))
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(len(archive.namelist()), len(TOP_FILES) + 1)
            with self.assertRaises(FileExistsError):
                package(root, output)

    def test_private_chat_in_docs_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.populate(root)
            (root / "docs").mkdir()
            (root / "docs/chat.md").write_text("synthetic", encoding="utf-8")
            with self.assertRaises(ValueError):
                release_files(root)


if __name__ == "__main__":
    unittest.main()
