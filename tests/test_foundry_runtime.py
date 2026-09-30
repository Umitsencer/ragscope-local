"""SDK-independent contract tests for the Foundry 2.x runtime adapter."""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ragscope.foundry import CHAT_TASKS, complete_chat, generate_embeddings, require_model_task


class FoundryRuntimeContractTests(unittest.TestCase):
    def test_missing_task_metadata_fails_before_native_session(self):
        model = Mock(info=SimpleNamespace(task=None))
        with self.assertRaisesRegex(RuntimeError, "catalog metadata"):
            require_model_task(model, CHAT_TASKS, "chat")

    def test_wrong_task_is_rejected(self):
        model = Mock(info=SimpleNamespace(task="embeddings"))
        with self.assertRaises(ValueError):
            require_model_task(model, CHAT_TASKS, "chat")

    def test_invalid_embedding_input_fails_before_sdk_import(self):
        with self.assertRaises(ValueError):
            generate_embeddings(Mock(), [""])

    def test_chat_configures_client_and_forwards_validated_messages(self):
        client = Mock(settings=SimpleNamespace())
        client.complete_chat.return_value = "synthetic response"
        model = Mock(
            info=SimpleNamespace(task="chat-completion"),
            get_chat_client=Mock(return_value=client),
        )
        messages = [{"role": "user", "content": "synthetic input"}]

        result = complete_chat(model, messages, max_output_tokens=17, temperature=0.25)

        self.assertEqual(result, "synthetic response")
        self.assertEqual(client.settings.temperature, 0.25)
        self.assertEqual(client.settings.max_tokens, 17)
        self.assertEqual(client.settings.response_format, {"type": "json_object"})
        client.complete_chat.assert_called_once_with(messages)

    def test_chat_rejects_invalid_message_before_client_creation(self):
        model = Mock(info=SimpleNamespace(task="chat-completion"))
        with self.assertRaisesRegex(ValueError, "Unsupported message"):
            complete_chat(
                model,
                [{"role": "tool", "content": "synthetic input"}],
                max_output_tokens=1,
            )
        model.get_chat_client.assert_not_called()

    def test_embeddings_restore_response_order(self):
        client = Mock()
        client.generate_embeddings.return_value = SimpleNamespace(
            data=[
                SimpleNamespace(index=1, embedding=[2.0] * 1024),
                SimpleNamespace(index=0, embedding=[1.0] * 1024),
            ]
        )
        model = Mock(
            info=SimpleNamespace(task="embeddings"),
            get_embedding_client=Mock(return_value=client),
        )

        vectors = generate_embeddings(model, ["first", "second"])

        self.assertEqual(vectors[0][0], 1.0)
        self.assertEqual(vectors[1][0], 2.0)
        client.generate_embeddings.assert_called_once_with(["first", "second"])

    def test_embeddings_reject_incomplete_batch(self):
        client = Mock()
        client.generate_embeddings.return_value = SimpleNamespace(
            data=[SimpleNamespace(index=0, embedding=[1.0] * 1024)]
        )
        model = Mock(
            info=SimpleNamespace(task="embeddings"),
            get_embedding_client=Mock(return_value=client),
        )
        with self.assertRaisesRegex(RuntimeError, "incomplete or misindexed embedding batch"):
            generate_embeddings(model, ["first", "second"])

    def test_embeddings_reject_duplicate_indices(self):
        client = Mock()
        client.generate_embeddings.return_value = SimpleNamespace(
            data=[
                SimpleNamespace(index=0, embedding=[1.0] * 1024),
                SimpleNamespace(index=0, embedding=[2.0] * 1024),
            ]
        )
        model = Mock(
            info=SimpleNamespace(task="embeddings"),
            get_embedding_client=Mock(return_value=client),
        )
        with self.assertRaisesRegex(RuntimeError, "misindexed embedding batch"):
            generate_embeddings(model, ["first", "second"])

    def test_embeddings_reject_dimension_drift(self):
        client = Mock()
        client.generate_embeddings.return_value = SimpleNamespace(
            data=[SimpleNamespace(index=0, embedding=[1.0] * 3)]
        )
        model = Mock(
            info=SimpleNamespace(task="embeddings"),
            get_embedding_client=Mock(return_value=client),
        )
        with self.assertRaisesRegex(RuntimeError, "embedding dimensions"):
            generate_embeddings(model, ["synthetic input"])


if __name__ == "__main__":
    unittest.main()
