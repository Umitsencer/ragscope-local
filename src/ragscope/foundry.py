"""Validated Foundry Local SDK 2.x adapter used by RAGScope Local."""

from __future__ import annotations

import importlib.metadata
import os

from ragscope.security import validate_chat_request, validate_embedding_inputs

SDK_PACKAGE = "foundry-local-sdk"
CHAT_TASKS = frozenset({"chat-completion", "vision-language-chat"})
EMBEDDING_DIMENSIONS = 1_024


def sdk_version() -> str:
    return importlib.metadata.version(SDK_PACKAGE)


def initialize_foundry(app_name: str):
    """Initialize SDK 2.x once with explicit, environment-configurable local paths."""
    from foundry_local_sdk import Configuration, FoundryLocalManager

    if FoundryLocalManager.instance is None:
        FoundryLocalManager.initialize(
            Configuration(
                app_name=app_name,
                app_data_dir=os.environ.get("RAGSCOPE_FOUNDRY_APP_DATA_DIR"),
                model_cache_dir=os.environ.get("RAGSCOPE_FOUNDRY_MODEL_CACHE_DIR"),
                disable_nonessential_telemetry=True,
            )
        )
    return FoundryLocalManager.instance


def require_model_task(model, allowed: set[str] | frozenset[str], purpose: str) -> str:
    """Fail clearly when catalog metadata cannot establish the model task."""
    task = getattr(getattr(model, "info", None), "task", None)
    if task not in allowed:
        if task is None:
            raise RuntimeError(
                f"Foundry catalog metadata lacks the model task required for {purpose}. "
                "Allow catalog metadata access, then retry. No model download is performed."
            )
        raise ValueError(f"Model task {task!r} is not valid for {purpose}")
    return task


def complete_chat(model, messages: list[dict], *, max_output_tokens: int, temperature: float = 0.0):
    """Run the measured SDK 2.0.1 compatibility path after strict validation."""
    validate_chat_request(messages, max_output_tokens=max_output_tokens, temperature=temperature)
    require_model_task(model, CHAT_TASKS, "chat")
    client = model.get_chat_client()
    client.settings.temperature = temperature
    client.settings.max_tokens = max_output_tokens
    client.settings.response_format = {"type": "json_object"}
    return client.complete_chat(messages)


def generate_embeddings(model, texts: list[str]) -> list[list[float]]:
    """Generate a bounded batch and reject incomplete or dimension-drifted output."""
    validate_embedding_inputs(texts)
    require_model_task(model, frozenset({"embeddings"}), "embeddings")
    response = model.get_embedding_client().generate_embeddings(texts)
    items = sorted(response.data, key=lambda item: item.index)
    if len(items) != len(texts) or [item.index for item in items] != list(range(len(texts))):
        raise RuntimeError("Foundry returned an incomplete or misindexed embedding batch")
    vectors = [list(item.embedding) for item in items]
    dimensions = {len(vector) for vector in vectors}
    if dimensions != {EMBEDDING_DIMENSIONS}:
        raise RuntimeError(f"Unexpected qwen3 embedding dimensions: {sorted(dimensions)}")
    return vectors
