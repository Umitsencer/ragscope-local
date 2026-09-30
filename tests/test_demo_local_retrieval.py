"""Synthetic evidence-card tests; Foundry runtime is not invoked."""

import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "demo_local_retrieval.py"
sys.path.insert(0, str(SCRIPT.parent))
spec = importlib.util.spec_from_file_location("demo_local_retrieval", SCRIPT)
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


class DemoEvidenceTests(unittest.TestCase):
    def test_only_measured_cross_sdk_cache_pair_is_allowed(self):
        self.assertTrue(demo.compatible_embedding_runtime("1.2.4", "2.0.1"))
        self.assertTrue(demo.compatible_embedding_runtime("2.0.1", "2.0.1"))
        self.assertFalse(demo.compatible_embedding_runtime("1.2.4", "2.1.0"))

    def test_invalid_vectors_are_rejected(self):
        for vector in ([], [0.0, 0.0], [float("nan"), 1], [float("inf")], [[1.0]]):
            with self.subTest(vector=vector), self.assertRaises(ValueError):
                demo.normalize(vector)

    def test_cache_provenance_coverage_and_vector_integrity(self):
        documents = [{"document_id": "T1", "name": "one", "description": "synthetic"}]
        header = {
            "kind": "header",
            "source_sha256": "source",
            "model_id": "model",
            "sdk_version": "sdk",
        }
        row = {
            "record_id": "T1",
            "text_sha256": hashlib.sha256(b"one\nsynthetic").hexdigest(),
            "vector": [1.0, 0.0],
        }
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "cache.jsonl"

            def write(rows):
                path.write_text("\n".join(json.dumps(item) for item in rows), encoding="utf-8")

            write([header, row])
            self.assertEqual(set(demo.load_corpus_cache(path, documents, "source")[0]), {"T1"})
            for rows in (
                [header],
                [header, row, row],
                [{**header, "source_sha256": "wrong"}, row],
                [header, {**row, "text_sha256": "wrong"}],
                [header, {**row, "vector": [float("nan")]}],
            ):
                write(rows)
                with self.assertRaises(ValueError):
                    demo.load_corpus_cache(path, documents, "source")

    def test_evidence_cards_rank_by_cosine_with_stable_ids(self):
        documents = [
            {
                "document_id": "T1",
                "name": "one",
                "description": "first",
                "is_subtechnique": False,
                "parent_technique_id": None,
            },
            {
                "document_id": "T2",
                "name": "two",
                "description": "second",
                "is_subtechnique": False,
                "parent_technique_id": None,
            },
        ]
        cards = demo.evidence_cards(documents, {"T1": [1.0, 0.0], "T2": [0.0, 1.0]}, [1.0, 0.0], 2)
        self.assertEqual([card["attack_id"] for card in cards], ["T1", "T2"])
        self.assertEqual(cards[0]["rank"], 1)

    def test_sibling_diagnostic_never_claims_a_gate_decision(self):
        cards = [{"attack_id": "T1.001"}]
        documents = [
            {"document_id": "T1", "parent_technique_id": None},
            {"document_id": "T1.001", "parent_technique_id": "T1"},
            {"document_id": "T1.002", "parent_technique_id": "T1"},
        ]
        diagnostic = demo.sibling_diagnostic(cards, documents)
        self.assertTrue(diagnostic["available"])
        self.assertIn("not enabled", diagnostic["message"])


if __name__ == "__main__":
    unittest.main()
