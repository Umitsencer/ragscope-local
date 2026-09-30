import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from diagnose_foundry_runtime import RuntimeProbe, Trace


class DiagnosticTests(unittest.TestCase):
    def test_trace_does_not_persist_error_message(self):
        stream = io.StringIO()

        def fail():
            raise RuntimeError("Operation was cancelled: synthetic-private-value")

        with self.assertRaises(RuntimeError):
            Trace(stream).call("completion", fail)
        self.assertNotIn("synthetic-private-value", stream.getvalue())
        self.assertTrue(json.loads(stream.getvalue().splitlines()[-1])["native_cancelled"])

    def test_runtime_probe_forwards_options_without_persisting_prompt(self):
        invoke = Mock(return_value="synthetic-result")
        stream = io.StringIO()
        model = Mock()
        result = RuntimeProbe(Trace(stream), invoke)(
            model,
            [{"role": "user", "content": "private synthetic input"}],
            max_output_tokens=7,
            temperature=0.0,
        )
        self.assertEqual(result, "synthetic-result")
        invoke.assert_called_once_with(
            model,
            [{"role": "user", "content": "private synthetic input"}],
            max_output_tokens=7,
            temperature=0.0,
        )
        self.assertNotIn("private synthetic input", stream.getvalue())
        self.assertIn("completion_1", stream.getvalue())


if __name__ == "__main__":
    unittest.main()
