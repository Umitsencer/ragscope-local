"""Fail-closed tests for local inference trust boundaries."""

import unittest

from ragscope.security import (
    MAX_CHAT_CONTEXT_CHARS,
    MAX_EMBEDDING_BATCH,
    MAX_OUTPUT_TOKENS,
    MAX_QUERY_CHARS,
    validate_chat_request,
    validate_embedding_inputs,
    validate_query,
)


class SecurityBoundaryTests(unittest.TestCase):
    def test_query_requires_bounded_safe_text(self):
        for value in ("", " ", "x" * (MAX_QUERY_CHARS + 1), "safe\x00unsafe"):
            with self.subTest(value=repr(value)[:30]), self.assertRaises(ValueError):
                validate_query(value)

    def test_chat_enforces_schema_and_resource_limits(self):
        with self.assertRaises(ValueError):
            validate_chat_request(
                [{"role": "user", "content": "x", "extra": "y"}],
                max_output_tokens=1,
                temperature=0.0,
            )
        with self.assertRaises(ValueError):
            validate_chat_request(
                [{"role": "user", "content": "x"}],
                max_output_tokens=MAX_OUTPUT_TOKENS + 1,
                temperature=0.0,
            )
        with self.assertRaises(ValueError):
            validate_chat_request(
                [{"role": "user", "content": "x" * (MAX_CHAT_CONTEXT_CHARS + 1)}],
                max_output_tokens=1,
                temperature=0.0,
            )

    def test_embedding_batch_rejects_over_limit_and_control_characters(self):
        with self.assertRaises(ValueError):
            validate_embedding_inputs(["x"] * (MAX_EMBEDDING_BATCH + 1))
        with self.assertRaises(ValueError):
            validate_embedding_inputs(["safe\x00unsafe"])


if __name__ == "__main__":
    unittest.main()
