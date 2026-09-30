"""Synthetic fixtures only; no third-party procedure text is embedded in tests."""

import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_mitre_procedure_benchmark.py"
spec = importlib.util.spec_from_file_location("build_mitre_procedure_benchmark", SCRIPT)
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


class MitreProcedureBenchmarkTests(unittest.TestCase):
    def test_groups_identical_text_as_multilabel_and_keeps_one_source_split(self):
        records = benchmark.group_queries(
            [
                {
                    "relationship_id": "r1",
                    "source_ref": "malware--a",
                    "source_type": "malware",
                    "target_id": "T1000.001",
                    "query_text": "Synthetic procedure",
                },
                {
                    "relationship_id": "r2",
                    "source_ref": "malware--a",
                    "source_type": "malware",
                    "target_id": "T1000.002",
                    "query_text": " Synthetic   procedure ",
                },
            ],
            seed="fixture",
        )
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["valid_target_ids"], ["T1000.001", "T1000.002"])
        self.assertEqual(records[0]["relationship_ids"], ["r1", "r2"])

    def test_rejects_identical_text_across_source_groups(self):
        with self.assertRaisesRegex(ValueError, "spans source groups"):
            benchmark.group_queries(
                [
                    {
                        "relationship_id": "r1",
                        "source_ref": "malware--a",
                        "source_type": "malware",
                        "target_id": "T1000",
                        "query_text": "Synthetic",
                    },
                    {
                        "relationship_id": "r2",
                        "source_ref": "tool--b",
                        "source_type": "tool",
                        "target_id": "T1001",
                        "query_text": "synthetic",
                    },
                ]
            )

    def test_extract_excludes_revoked_and_non_technique_targets(self):
        objects = [
            {
                "type": "attack-pattern",
                "id": "tech",
                "external_references": [{"source_name": "mitre-attack", "external_id": "T1000"}],
            },
            {
                "type": "attack-pattern",
                "id": "old",
                "revoked": True,
                "external_references": [{"source_name": "mitre-attack", "external_id": "T1001"}],
            },
            {
                "type": "relationship",
                "id": "keep",
                "relationship_type": "uses",
                "source_ref": "malware--a",
                "target_ref": "tech",
                "description": " Synthetic use ",
            },
            {
                "type": "relationship",
                "id": "drop",
                "relationship_type": "uses",
                "source_ref": "malware--a",
                "target_ref": "old",
                "description": "Synthetic old",
            },
        ]
        rows = benchmark.extract_relationship_rows(objects)
        self.assertEqual(
            rows,
            [
                {
                    "relationship_id": "keep",
                    "source_ref": "malware--a",
                    "source_type": "malware",
                    "target_id": "T1000",
                    "query_text": "Synthetic use",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
