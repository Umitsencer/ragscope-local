"""Synthetic tests for SAGE math and decision boundaries only."""

import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_sage_ablation.py"
sys.path.insert(0, str(SCRIPT.parent))
spec = importlib.util.spec_from_file_location("run_sage_ablation", SCRIPT)
sage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sage)


class SageAblationTests(unittest.TestCase):
    def setUp(self):
        self.feature = {
            "query_id": "synthetic-q",
            "gold_ids": ["T1.001"],
            "dense_top": "T1.001",
            "dense_top_score": 0.8,
            "family_parent": "T1",
            "sibling_supported": True,
            "siblings": ["T1.001", "T1.002"],
            "dense_z": [1.0, -1.0],
            "bm25_z": [0.0, 0.0],
        }

    def test_margin_gate_returns_child_parent_and_abstain(self):
        self.assertEqual(sage.decide(self.feature, 0.0, 1.0, 0.0)["decision"], "child")
        self.assertEqual(sage.decide(self.feature, 0.0, 3.0, 0.0)["decision"], "parent")
        self.assertEqual(sage.decide(self.feature, 0.0, 1.0, 0.9)["decision"], "abstain")

    def test_exact_upper_bound_is_conservative_for_zero_errors(self):
        bound = sage.clopper_pearson_upper(0, 20)
        self.assertGreater(bound, 0.13)
        self.assertLess(bound, 0.15)

    def test_unsupported_family_is_passthrough(self):
        feature = {**self.feature, "sibling_supported": False}
        self.assertEqual(sage.decide(feature, 0.0, 0.0, 0.0)["decision"], "dense_passthrough")

    def test_frozen_config_rejects_wrong_split_hash_and_mode(self):
        config = {"alpha": 0.5, "margin_threshold": -1e9, "score_threshold": -1e9}
        artifact = {
            "run": "sage-attack-ranking-dev-selection-v0",
            "split": "dev",
            "test_split_accessed": False,
            "corpus_sha256": "c",
            "benchmark_sha256": "b",
            "selected_config": config,
        }
        self.assertEqual(
            sage.validate_frozen_config(artifact, "ranking-evaluate", "c", "b"), config
        )
        for override in (
            {"split": "test"},
            {"corpus_sha256": "wrong"},
            {"test_split_accessed": True},
            {"selected_config": None},
        ):
            with self.assertRaises(ValueError):
                sage.validate_frozen_config({**artifact, **override}, "ranking-evaluate", "c", "b")
        with self.assertRaises(ValueError):
            sage.validate_frozen_config(artifact, "evaluate", "c", "b")


if __name__ == "__main__":
    unittest.main()
