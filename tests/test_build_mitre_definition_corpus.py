"""Synthetic fixtures only; no third-party procedure text is embedded in tests."""

import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_mitre_definition_corpus.py"
spec = importlib.util.spec_from_file_location("build_mitre_definition_corpus", SCRIPT)
corpus = importlib.util.module_from_spec(spec)
spec.loader.exec_module(corpus)


class MitreDefinitionCorpusTests(unittest.TestCase):
    def test_builds_active_attack_patterns_only(self):
        objects = [
            {
                "type": "attack-pattern",
                "id": "parent",
                "name": "Synthetic Parent",
                "description": " Parent definition ",
                "external_references": [{"source_name": "mitre-attack", "external_id": "T1000"}],
            },
            {
                "type": "attack-pattern",
                "id": "child",
                "name": "Synthetic Child",
                "description": "Child definition",
                "x_mitre_is_subtechnique": True,
                "external_references": [
                    {"source_name": "mitre-attack", "external_id": "T1000.001"}
                ],
            },
            {
                "type": "attack-pattern",
                "id": "old",
                "name": "Old",
                "description": "Old definition",
                "revoked": True,
                "external_references": [{"source_name": "mitre-attack", "external_id": "T1001"}],
            },
            {
                "type": "relationship",
                "relationship_type": "subtechnique-of",
                "source_ref": "child",
                "target_ref": "parent",
            },
            {
                "type": "relationship",
                "relationship_type": "uses",
                "source_ref": "malware--a",
                "target_ref": "child",
                "description": "Synthetic procedure",
            },
        ]
        documents = corpus.build_documents(objects)
        self.assertEqual(
            [document["document_id"] for document in documents], ["T1000", "T1000.001"]
        )
        self.assertEqual(documents[1]["parent_technique_id"], "T1000")
        self.assertEqual(documents[0]["description"], "Parent definition")

    def test_audit_reports_no_relationship_input_and_detects_exact_overlap(self):
        documents = [
            {"document_id": "T1000", "description": "Synthetic procedure", "is_subtechnique": False}
        ]
        objects = [
            {
                "type": "relationship",
                "relationship_type": "uses",
                "description": "synthetic procedure",
            }
        ]
        result = corpus.corpus_audit(documents, objects)
        self.assertEqual(result["relationship_objects_used_as_corpus_input"], 0)
        self.assertEqual(result["uses_procedure_descriptions_used_as_corpus_input"], 0)
        self.assertEqual(result["exact_normalized_uses_description_equals_definition_count"], 1)


if __name__ == "__main__":
    unittest.main()
