"""Cache-writer concurrency protection uses only temporary synthetic paths."""

import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_foundry_embedding_cache.py"
spec = importlib.util.spec_from_file_location("build_foundry_embedding_cache", SCRIPT)
cache_builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cache_builder)


class CacheLockTests(unittest.TestCase):
    def test_second_writer_is_rejected_while_first_writer_holds_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            cache_path = Path(directory) / "synthetic.jsonl"
            with (
                cache_builder.exclusive_cache_lock(cache_path),
                self.assertRaisesRegex(RuntimeError, "writer already active"),
                cache_builder.exclusive_cache_lock(cache_path),
            ):
                pass
            self.assertFalse(cache_path.with_suffix(".jsonl.lock").exists())


if __name__ == "__main__":
    unittest.main()
