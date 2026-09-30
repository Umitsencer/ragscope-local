import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from verify_acceptance_integrity import portable_text_digests, verify


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

    def test_portable_text_digests_newline_equivalence_and_strict_content_integrity(self):
        """Security boundary: portable_text_digests only equates LF and CRLF line endings.

        Any semantic or character change must produce non-matching hashes.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            lf_file = tmppath / "corpus_lf.jsonl"
            crlf_file = tmppath / "corpus_crlf.jsonl"
            tampered_file = tmppath / "corpus_tampered.jsonl"

            sample_text = (
                '{"document_id": "T1001", "name": "Data Obfuscation"}\n'
                '{"document_id": "T1002", "name": "Data Compressed"}\n'
            )
            lf_file.write_bytes(sample_text.encode("utf-8"))
            crlf_file.write_bytes(sample_text.replace("\n", "\r\n").encode("utf-8"))
            tampered_file.write_bytes(sample_text.replace("Data", "Info").encode("utf-8"))

            lf_digests = portable_text_digests(lf_file)
            crlf_digests = portable_text_digests(crlf_file)

            # Both LF and CRLF versions must generate identical digest sets
            self.assertEqual(lf_digests, crlf_digests)
            self.assertEqual(len(lf_digests), 2)

            expected_lf_hash = hashlib.sha256(sample_text.encode("utf-8")).hexdigest()
            expected_crlf_hash = hashlib.sha256(
                sample_text.replace("\n", "\r\n").encode("utf-8")
            ).hexdigest()
            self.assertIn(expected_lf_hash, lf_digests)
            self.assertIn(expected_crlf_hash, lf_digests)

            # Tampered content must NOT match either digest
            tampered_hash = hashlib.sha256(tampered_file.read_bytes()).hexdigest()
            self.assertNotIn(tampered_hash, lf_digests)


if __name__ == "__main__":
    unittest.main()
