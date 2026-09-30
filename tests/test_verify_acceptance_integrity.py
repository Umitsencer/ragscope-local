import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from verify_acceptance_integrity import verify


class AcceptanceIntegrityTests(unittest.TestCase):
    def test_canonical_sdk2_run_has_intact_sources_and_manifests(self):
        run_dir = (
            Path(__file__).resolve().parents[1] / "data/acceptance/2026-09-28-deployment-final"
        )
        report = verify(run_dir)
        self.assertTrue(report["integrity_passed"], report["errors"])
        self.assertEqual(report["cases_checked"], 6)
        self.assertEqual(report["quotes_checked"], 5)
        self.assertTrue(report["orchestration_script_manifest_match"])


if __name__ == "__main__":
    unittest.main()
