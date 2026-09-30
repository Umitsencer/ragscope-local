"""Synthetic AnnoCTR audit fixtures."""

import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("audit_annoctr", SCRIPTS / "audit_annoctr.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class AnnoCTRAuditTests(unittest.TestCase):
    def test_technique_url_parser(self):
        self.assertEqual(
            audit.technique_id("https://attack.mitre.org/techniques/T1059/001"), "T1059.001"
        )
        self.assertEqual(audit.technique_id("https://attack.mitre.org/techniques/T1059/"), "T1059")
        self.assertIsNone(audit.technique_id("https://attack.mitre.org/software/S0001"))

    def test_split_counts_only_active_enterprise_children(self):
        rows = [
            {
                "document": "synthetic-1",
                "entity_type": "TECHNIQUE",
                "label_link": "https://attack.mitre.org/techniques/T1059/001",
            },
            {
                "document": "synthetic-2",
                "entity_type": "TECHNIQUE",
                "label_link": "https://attack.mitre.org/techniques/T1631/001",
            },
            {
                "document": "synthetic-2",
                "entity_type": "MALWARE",
                "label_link": "https://attack.mitre.org/software/S0001",
            },
        ]
        result = audit.audit_split(rows, {"T1059.001"}, {"T1059.001": "T1059"})
        self.assertEqual(result["subtechnique_url_rows"], 2)
        self.assertEqual(result["active_enterprise_19_2_subtechnique_rows"], 1)
        self.assertEqual(result["unique_documents_all_rows"], 2)


if __name__ == "__main__":
    unittest.main()
