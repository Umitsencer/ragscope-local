"""Synthetic runner tests; never invoke a model or network."""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from run_rag_acceptance import CASES_PATH, assess_process, load_cases


class AcceptanceTests(unittest.TestCase):
    def test_extractive_output_requires_matching_mode(self):
        output = json.dumps(
            {
                "run": "ragscope-local-extractive-demo-v1",
                "generation": {"status": "evidence_selected"},
            }
        )
        self.assertTrue(assess_process(0, output, "extractive")["process_ok"])
        self.assertFalse(assess_process(0, output)["process_ok"])

    def test_fixed_cases_exist(self):
        cases = load_cases(CASES_PATH)
        self.assertEqual(len(cases), 6)
        self.assertEqual(len({row["id"] for row in cases}), 6)

    def test_failure_is_not_success(self):
        for code, output in ((1, "{}"), (0, "garbage"), (0, "[]"), (0, "{}")):
            self.assertFalse(assess_process(code, output)["process_ok"])

    def test_rejection_is_recorded_not_hidden(self):
        output = {"run": "ragscope-local-rag-demo-v0", "generation": {"status": "rejected_output"}}
        result = assess_process(0, json.dumps(output))
        self.assertEqual(result["outcome"], "rejected_output")
        self.assertEqual(result["semantic_review"], "pending")


if __name__ == "__main__":
    unittest.main()
