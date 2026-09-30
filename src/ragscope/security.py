"""Fail-closed validation at the local model and retrieval trust boundaries."""

from __future__ import annotations

from collections.abc import Sequence
from numbers import Real

MAX_QUERY_CHARS = 4_000
MAX_CHAT_MESSAGES = 16
MAX_CHAT_MESSAGE_CHARS = 32_000
MAX_CHAT_CONTEXT_CHARS = 64_000
MAX_OUTPUT_TOKENS = 512
MAX_EMBEDDING_BATCH = 64
MAX_EMBEDDING_TEXT_CHARS = 16_000
ALLOWED_CHAT_ROLES = frozenset({"system", "developer", "user", "assistant"})


def _contains_disallowed_control(text: str) -> bool:
    return any(ord(character) < 32 and character not in "\t\r\n" for character in text)


def validate_query(query: str) -> str:
    """Validate bounded, textual user input without attempting semantic filtering."""
    if (
        not isinstance(query, str)
        or not query.strip()
        or len(query) > MAX_QUERY_CHARS
        or _contains_disallowed_control(query)
    ):
        raise ValueError(f"Query must contain 1-{MAX_QUERY_CHARS} safe text characters")
    return query


def validate_chat_request(
    messages: Sequence[dict], *, max_output_tokens: int, temperature: float
) -> None:
    """Bound model resource use and reject ambiguous message schemas."""
    if not messages or len(messages) > MAX_CHAT_MESSAGES:
        raise ValueError(f"Chat requires 1-{MAX_CHAT_MESSAGES} messages")
    if (
        isinstance(max_output_tokens, bool)
        or not isinstance(max_output_tokens, int)
        or not 1 <= max_output_tokens <= MAX_OUTPUT_TOKENS
    ):
        raise ValueError(f"Output-token limit must be between 1 and {MAX_OUTPUT_TOKENS}")
    if (
        isinstance(temperature, bool)
        or not isinstance(temperature, Real)
        or not 0.0 <= float(temperature) <= 2.0
    ):
        raise ValueError("Temperature must be a finite number between 0 and 2")

    total_chars = 0
    for index, message in enumerate(messages):
        if (
            not isinstance(message, dict)
            or set(message) != {"role", "content"}
            or message.get("role") not in ALLOWED_CHAT_ROLES
            or not isinstance(message.get("content"), str)
            or not message["content"]
            or len(message["content"]) > MAX_CHAT_MESSAGE_CHARS
            or _contains_disallowed_control(message["content"])
        ):
            raise ValueError(f"Unsupported message at index {index}")
        total_chars += len(message["content"])
    if total_chars > MAX_CHAT_CONTEXT_CHARS:
        raise ValueError(f"Chat context exceeds {MAX_CHAT_CONTEXT_CHARS} characters")


def validate_embedding_inputs(texts: Sequence[str]) -> None:
    """Bound embedding batch and document size before native runtime allocation."""
    if not texts or len(texts) > MAX_EMBEDDING_BATCH:
        raise ValueError(f"Embedding batch must contain 1-{MAX_EMBEDDING_BATCH} texts")
    for index, text in enumerate(texts):
        if (
            not isinstance(text, str)
            or not text.strip()
            or len(text) > MAX_EMBEDDING_TEXT_CHARS
            or _contains_disallowed_control(text)
        ):
            raise ValueError(f"Invalid embedding text at index {index}")
