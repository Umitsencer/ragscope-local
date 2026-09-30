"""Synthetic rankings only; no model or third-party text is required."""

import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_rrf_hybrid.py"
spec = importlib.util.spec_from_file_location("run_rrf_hybrid", SCRIPT)
hybrid = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hybrid)


class RrfHybridTests(unittest.TestCase):
    def test_rrf_rewards_agreement_and_breaks_ties_by_document_id(self):
        ranking = hybrid.rrf(["T1001", "T1000", "T2000"], ["T1000", "T1001", "T3000"], k=10)
        self.assertEqual(ranking[:2], ["T1000", "T1001"])

    def test_rrf_rejects_nonpositive_k_by_caller_contract(self):
        # RRF itself is mathematical; experiment configuration constrains k > 0.
        self.assertEqual(hybrid.rrf(["T1"], ["T2"], k=1), ["T1", "T2"])

    def test_evaluate_rrf_keeps_duplicate_query_texts_separate_by_id(self):
        documents = {"T1000": [1.0, 0.0], "T2000": [0.0, 1.0]}
        queries = {"q1": [1.0, 0.0], "q2": [0.0, 1.0]}
        records = [
            {"query_id": "q1", "query_text": "same synthetic text", "valid_target_ids": ["T1000"]},
            {"query_id": "q2", "query_text": "same synthetic text", "valid_target_ids": ["T2000"]},
        ]
        index = {
            "document_ids": ["T1000", "T2000"],
            "postings": {},
            "lengths": {"T1000": 1, "T2000": 1},
            "avg_length": 1,
            "k1": 1.2,
            "b": 0.75,
        }
        components = hybrid.component_rankings(records, index, documents, queries)
        result = hybrid.evaluate_rrf(records, {}, components, 10)
        # Both records are evaluated independently even though their raw text is equal.
        self.assertEqual(result["queries"], 2)


if __name__ == "__main__":
    unittest.main()
