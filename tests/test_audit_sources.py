"""Synthetic fixtures only; no third-party text is embedded in tests."""

import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "audit_sources.py"
spec = importlib.util.spec_from_file_location("audit_sources", SCRIPT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class AuditSourceTests(unittest.TestCase):
    def test_attack_mapping_excludes_revoked_and_preserves_parent(self):
        objects = [
            {
                "type": "attack-pattern",
                "id": "parent",
                "external_references": [{"source_name": "mitre-attack", "external_id": "T1000"}],
            },
            {
                "type": "attack-pattern",
                "id": "child",
                "x_mitre_is_subtechnique": True,
                "external_references": [
                    {"source_name": "mitre-attack", "external_id": "T1000.001"}
                ],
            },
            {
                "type": "attack-pattern",
                "id": "old",
                "revoked": True,
                "external_references": [{"source_name": "mitre-attack", "external_id": "T1001"}],
            },
            {
                "type": "relationship",
                "relationship_type": "subtechnique-of",
                "source_ref": "child",
                "target_ref": "parent",
            },
        ]
        external, parents, counts = audit.attack_mapping(objects)
        self.assertEqual(parents, {"T1000.001": "T1000"})
        self.assertTrue(external["T1001"]["revoked"])
        self.assertEqual(counts["active_techniques"], 1)
        self.assertEqual(counts["active_subtechniques"], 1)

    def test_ata_audit_detects_duplicate_and_sibling_family(self):
        external = {
            "T1000": {"id": "parent"},
            "T1000.001": {"id": "child1"},
            "T1000.002": {"id": "child2"},
        }
        rows = [
            {
                "id": "a",
                "question": "Synthetic alpha",
                "source": {"source_id": "source-1"},
                "ground_truth": {"target_ids": ["T1000.001"]},
            },
            {
                "id": "b",
                "question": "Synthetic alpha",
                "source": {"source_id": "source-1"},
                "ground_truth": {"target_ids": ["T1000.002"]},
            },
            {
                "id": "c",
                "question": "Synthetic parent",
                "source": {"source_id": "source-2"},
                "ground_truth": {"target_ids": ["T1000"]},
            },
        ]
        result = audit.audit_ata(rows, external, {"T1000.001": "T1000", "T1000.002": "T1000"})
        self.assertEqual(result["sibling_family_count"], 1)
        self.assertEqual(result["parent_and_child_family_count"], 1)
        self.assertEqual(result["unique_source_ids"], 2)
        self.assertEqual(result["exact_duplicate_question_record_groups"], [["a", "b"]])
        self.assertEqual(len(result["conflicting_duplicate_questions"]), 1)
        self.assertEqual(result["question_contains_gold_id_count"], 0)


if __name__ == "__main__":
    unittest.main()
