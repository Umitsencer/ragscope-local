"""Checkpoint local Foundry embeddings for reproducible dense/hybrid runs.

Cache files are local acceleration artifacts, ignored by Git. Each cache binds
model ID and source SHA-256 to its vectors, resumes safely by record ID, and
never sends text to a cloud API.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from contextlib import contextmanager
from pathlib import Path

from audit_sources import ROOT, sha256
from run_bm25_baseline import read_jsonl

from ragscope.foundry import generate_embeddings, initialize_foundry, sdk_version

CORPUS_PATH = ROOT / "data/derived/mitre_definition_corpus.jsonl"
BENCHMARK_PATH = ROOT / "data/derived/mitre_procedure_benchmark.jsonl"
CACHE_DIR = ROOT / "data/local_cache"
MODEL_ALIAS = "qwen3-embedding-0.6b"


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize(vector: list[float]) -> list[float]:
    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude == 0:
        raise ValueError("Foundry returned a zero embedding vector")
    return [value / magnitude for value in vector]


def cache_path(kind: str, split: str | None) -> Path:
    suffix = kind if split is None else f"{kind}_{split}"
    return CACHE_DIR / f"foundry_qwen3_embedding_0_6b_{suffix}.jsonl"


@contextmanager
def exclusive_cache_lock(path: Path):
    """Prevent concurrent writers from corrupting a resumable JSONL cache."""
    lock_path = path.with_suffix(path.suffix + ".lock")
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        raise RuntimeError(
            f"Cache writer already active or stale lock remains: {lock_path}. "
            "Verify no writer is running before removing a stale lock."
        ) from error
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump({"pid": os.getpid(), "cache_path": str(path)}, stream, sort_keys=True)
        yield
    finally:
        lock_path.unlink(missing_ok=True)


def read_cache(path: Path, expected: dict) -> set[str]:
    if not path.exists():
        return set()
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        return set()
    header = json.loads(lines[0])
    if header.get("kind") != "header" or any(
        header.get(key) != value for key, value in expected.items()
    ):
        raise ValueError(f"Cache provenance mismatch: {path}")
    return {json.loads(line)["record_id"] for line in lines[1:] if line.strip()}


def source_records(kind: str, split: str | None) -> tuple[list[dict], str]:
    if kind == "corpus":
        records = [
            {"record_id": row["document_id"], "text": row["name"] + "\n" + row["description"]}
            for row in read_jsonl(CORPUS_PATH)
        ]
        return records, sha256(CORPUS_PATH)
    records = [
        {"record_id": row["query_id"], "text": row["query_text"]}
        for row in read_jsonl(BENCHMARK_PATH)
        if row["split"] == split
    ]
    return records, sha256(BENCHMARK_PATH)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=("corpus", "queries"), required=True)
    parser.add_argument("--split", choices=("train", "dev", "test"))
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--allow-model-download", action="store_true")
    args = parser.parse_args()
    if (args.kind == "queries") != (args.split is not None):
        raise ValueError("queries require --split; corpus must omit --split")
    records, source_sha = source_records(args.kind, args.split)
    manager = initialize_foundry("ragscope_foundry_cache")
    model = manager.catalog.get_model(MODEL_ALIAS)
    if model is None:
        raise ValueError(f"Required catalog alias absent: {MODEL_ALIAS}")
    if not model.is_cached:
        if not args.allow_model_download:
            raise RuntimeError("Model is not cached; explicit --allow-model-download required")
        model.download()
    expected = {"source_sha256": source_sha, "model_id": model.id, "sdk_version": sdk_version()}
    path = cache_path(args.kind, args.split)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with exclusive_cache_lock(path):
        completed = read_cache(path, expected)
        pending = [record for record in records if record["record_id"] not in completed]
        if not path.exists() or path.stat().st_size == 0:
            path.write_text(
                json.dumps({"kind": "header", **expected}, sort_keys=True) + "\n", encoding="utf-8"
            )
        if not pending:
            print(f"Cache complete: {path}; records: {len(records)}")
            return
        try:
            model.load()
            with path.open("a", encoding="utf-8") as stream:
                for start in range(0, len(pending), args.batch_size):
                    batch = pending[start : start + args.batch_size]
                    vectors = generate_embeddings(model, [record["text"] for record in batch])
                    for record, vector in zip(batch, vectors, strict=True):
                        stream.write(
                            json.dumps(
                                {
                                    "record_id": record["record_id"],
                                    "text_sha256": text_hash(record["text"]),
                                    "vector": normalize(vector),
                                },
                                separators=(",", ":"),
                            )
                            + "\n"
                        )
                    stream.flush()
                    print(
                        f"Cached {min(start + len(batch), len(pending))}/{len(pending)} pending records",
                        flush=True,
                    )
        finally:
            if model.is_loaded:
                model.unload()
        print(f"Cache complete: {path}; records: {len(records)}")


if __name__ == "__main__":
    main()
