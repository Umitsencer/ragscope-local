"""Synthetic vector fixtures only; Foundry Local is not required for these tests."""

import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_foundry_dense_baseline.py"
spec = importlib.util.spec_from_file_location("run_foundry_dense_baseline", SCRIPT)
dense = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dense)


class DenseBaselineTests(unittest.TestCase):
    def test_cosine_ranking_uses_deterministic_id_tie_break(self):
        ranking = dense.cosine_ranking(
            [1.0, 0.0], {"T1001": [1.0, 0.0], "T1000": [1.0, 0.0], "T2000": [0.0, 1.0]}
        )
        self.assertEqual(ranking, ["T1000", "T1001", "T2000"])

    def test_cosine_ranking_rejects_dimension_mismatch(self):
        with self.assertRaises(ValueError):
            dense.cosine_ranking([1.0, 0.0], {"T1000": [1.0]})

    def test_evaluate_credits_multilabel_gold(self):
        records = [{"query_vector": [1.0, 0.0], "valid_target_ids": ["T1000", "T1000.001"]}]
        vectors = {"T1000": [1.0, 0.0], "T1000.001": [0.5, 0.5], "T2000": [0.0, 1.0]}
        result = dense.evaluate(records, vectors, {"T1000.001": "T1000"})
        self.assertEqual(result["query_macro_metrics"]["hit_at_1"], 1.0)
        self.assertEqual(result["query_macro_metrics"]["recall_at_1"], 0.5)
        self.assertIn("T1000", result["subtechnique_family_metrics"])


if __name__ == "__main__":
    unittest.main()
