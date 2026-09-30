"""Synthetic fixtures only; no third-party procedure text is embedded in tests."""

import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_bm25_baseline.py"
spec = importlib.util.spec_from_file_location("run_bm25_baseline", SCRIPT)
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)


class Bm25BaselineTests(unittest.TestCase):
    def setUp(self):
        self.documents = [
            {
                "document_id": "T1000",
                "name": "Synthetic Parent",
                "description": "network copy utility",
                "parent_technique_id": None,
            },
            {
                "document_id": "T1000.001",
                "name": "Synthetic Child",
                "description": "network copy transfer",
                "parent_technique_id": "T1000",
            },
            {
                "document_id": "T2000",
                "name": "Other",
                "description": "unrelated registry setting",
                "parent_technique_id": None,
            },
        ]

    def test_ranking_is_deterministic_and_prefers_matching_document(self):
        ranking = baseline.rank(baseline.build_bm25(self.documents), "network copy transfer")
        self.assertEqual(ranking[0], "T1000.001")

    def test_multilabel_metrics_credit_any_valid_target(self):
        index = baseline.build_bm25(self.documents)
        records = [
            {"query_text": "network copy transfer", "valid_target_ids": ["T1000", "T1000.001"]}
        ]
        result = baseline.evaluate(records, index, baseline.parent_mapping(self.documents))
        self.assertEqual(result["queries"], 1)
        self.assertEqual(result["query_macro_metrics"]["hit_at_1"], 1.0)
        self.assertEqual(result["query_macro_metrics"]["recall_at_1"], 0.5)
        self.assertIn("T1000", result["subtechnique_family_metrics"])


if __name__ == "__main__":
    unittest.main()
