"""Synthetic paired-analysis tests; no MITRE query text or model is needed."""

import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "analyze_sage_ablation.py"
sys.path.insert(0, str(SCRIPT.parent))
spec = importlib.util.spec_from_file_location("analyze_sage_ablation", SCRIPT)
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)


class SageAnalysisTests(unittest.TestCase):
    def test_paired_counts_and_bootstrap_are_deterministic(self):
        traces = [
            {
                "dense_top": "A",
                "output_id": "B",
                "gold_ids": ["B"],
                "family_parent": "T1",
                "sibling_supported": True,
            },
            {
                "dense_top": "A",
                "output_id": "B",
                "gold_ids": ["A"],
                "family_parent": "T1",
                "sibling_supported": True,
            },
            {
                "dense_top": "A",
                "output_id": "A",
                "gold_ids": ["A"],
                "family_parent": "T1",
                "sibling_supported": True,
            },
            {
                "dense_top": "A",
                "output_id": "B",
                "gold_ids": ["C"],
                "family_parent": "T1",
                "sibling_supported": True,
            },
        ]
        result = analysis.analyze(traces, minimum_family_queries=1)
        self.assertEqual(result["sage_only_correct"], 1)
        self.assertEqual(result["dense_only_correct"], 1)
        self.assertEqual(result["both_correct"], 1)
        self.assertEqual(result["both_incorrect"], 1)
        self.assertEqual(result["paired_bootstrap"]["observed_delta"], 0.0)
        self.assertEqual(result["paired_bootstrap"]["seed"], 20260920)


if __name__ == "__main__":
    unittest.main()
