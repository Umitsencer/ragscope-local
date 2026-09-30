"""Run an evidence-first local Foundry retrieval demonstration.

The command performs local embedding and retrieval only.  It deliberately does
not generate an answer or present the unvalidated SAGE M3 gate as a decision.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from audit_sources import sha256
from build_foundry_embedding_cache import MODEL_ALIAS, cache_path
from run_bm25_baseline import CORPUS_PATH, parent_mapping, read_jsonl

from ragscope.foundry import generate_embeddings, initialize_foundry, sdk_version
from ragscope.security import validate_query

VERIFIED_CACHE_RUNTIME_PAIRS = {frozenset({"1.2.4", "2.0.1"})}


def compatible_embedding_runtime(cache_version: str, runtime_version: str) -> bool:
    """Allow only numerically checked cross-SDK cache reuse for this model."""
    return (
        cache_version == runtime_version
        or frozenset({cache_version, runtime_version}) in VERIFIED_CACHE_RUNTIME_PAIRS
    )


def normalize(vector: list[float]) -> np.ndarray:
    values = np.asarray(vector, dtype=np.float32)
    if values.ndim != 1 or not values.size or not np.isfinite(values).all():
        raise ValueError("Embedding must be a non-empty finite vector")
    magnitude = float(np.linalg.norm(values))
    if not np.isfinite(magnitude) or magnitude == 0.0:
        raise ValueError("Foundry returned a zero query embedding")
    return values / magnitude


def load_corpus_cache(path: Path, documents: list[dict], corpus_sha: str) -> tuple[dict, dict]:
    """Reject stale, incomplete or malformed demo caches before inference."""
    rows = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    if not rows or rows[0].get("kind") != "header" or rows[0].get("source_sha256") != corpus_sha:
        raise ValueError("Corpus cache provenance mismatch")
    header = rows[0]
    if not header.get("model_id") or not header.get("sdk_version"):
        raise ValueError("Corpus cache lacks model/SDK provenance")
    expected = {
        row["document_id"]: hashlib.sha256(
            (row["name"] + "\n" + row["description"]).encode("utf-8")
        ).hexdigest()
        for row in documents
    }
    if len(expected) != len(documents):
        raise ValueError("Duplicate document IDs in corpus")
    vectors = {}
    dimension = None
    for row in rows[1:]:
        record_id = row["record_id"]
        if (
            record_id in vectors
            or record_id not in expected
            or row.get("text_sha256") != expected[record_id]
        ):
            raise ValueError("Corpus cache has duplicate, unknown or stale records")
        vector = normalize(row["vector"])
        if dimension is not None and vector.size != dimension:
            raise ValueError("Corpus cache vector dimensions differ")
        dimension = vector.size
        vectors[record_id] = vector.tolist()
    if not vectors or set(vectors) != set(expected):
        raise ValueError("Corpus cache is incomplete")
    return vectors, header


def evidence_cards(
    documents: list[dict],
    document_vectors: dict[str, list[float]],
    query_vector: list[float],
    top_k: int,
) -> list[dict]:
    """Create deterministic source cards, including only definition-corpus fields."""
    by_id = {document["document_id"]: document for document in documents}
    if not 1 <= top_k <= 20 or not document_vectors or set(document_vectors) != set(by_id):
        raise ValueError("Invalid top-k or corpus/cache coverage")
    document_ids = sorted(document_vectors)
    matrix = np.asarray(
        [normalize(document_vectors[document_id]) for document_id in document_ids], dtype=np.float32
    )
    scores = matrix @ normalize(query_vector)
    ordering = np.argsort(-scores, kind="stable")[:top_k]
    return [
        {
            "rank": position,
            "attack_id": document_ids[index],
            "name": by_id[document_ids[index]]["name"],
            "is_subtechnique": by_id[document_ids[index]]["is_subtechnique"],
            "parent_technique_id": by_id[document_ids[index]]["parent_technique_id"],
            "cosine_similarity": float(scores[index]),
            "definition": by_id[document_ids[index]]["description"],
        }
        for position, index in enumerate(ordering, start=1)
    ]


def sibling_diagnostic(cards: list[dict], documents: list[dict]) -> dict:
    """Expose family context without presenting a granularity decision as validated."""
    if not cards:
        return {"available": False, "reason": "no_retrieval_result"}
    parents = parent_mapping(documents)
    top = cards[0]
    parent = parents.get(top["attack_id"], top["attack_id"])
    siblings = sorted(child for child, family in parents.items() if family == parent)
    return {
        "available": len(siblings) >= 2,
        "top_result_parent_family": parent,
        "family_child_ids": siblings,
        "message": "SAGE M3 child/parent/abstain gate is not enabled: its controlled dev calibration did not meet the declared risk bound.",
    }


def local_embedding(
    query: str, expected_cache_header: dict | None = None
) -> tuple[list[float], dict]:
    """Embed one user-provided query through the installed, already-cached local model."""
    manager = initialize_foundry("ragscope_local_demo")
    model = manager.catalog.get_model(MODEL_ALIAS)
    if model is None:
        raise RuntimeError(f"Foundry catalog does not expose required alias: {MODEL_ALIAS}")
    if not model.is_cached:
        raise RuntimeError(
            "Required local model is not cached. Review license/catalog metadata before any explicit download; this demo never downloads a model."
        )
    installed_sdk = sdk_version()
    if expected_cache_header is not None and (
        model.id != expected_cache_header["model_id"]
        or not compatible_embedding_runtime(expected_cache_header["sdk_version"], installed_sdk)
    ):
        raise ValueError("Query model/SDK differs from the verified corpus-cache compatibility set")
    try:
        model.load()
        vectors = generate_embeddings(model, [query])
        return vectors[0], {
            "model_id": model.id,
            "sdk_version": installed_sdk,
            "cache_sdk_version": expected_cache_header.get("sdk_version")
            if expected_cache_header
            else None,
            "runtime_device": str(model.info.runtime.device_type),
            "local_inference": True,
        }
    finally:
        if model.is_loaded:
            model.unload()


def retrieve(query: str, top_k: int = 5) -> dict:
    """Retrieve source evidence without mutating benchmark or cache files."""
    validate_query(query)
    if not 1 <= top_k <= 20:
        raise ValueError("top-k must be 1–20")
    corpus_sha = sha256(CORPUS_PATH)
    documents = read_jsonl(CORPUS_PATH)
    vectors, header = load_corpus_cache(cache_path("corpus", None), documents, corpus_sha)
    query_vector, runtime = local_embedding(query, header)
    cards = evidence_cards(documents, vectors, query_vector, top_k)
    return {
        "query_sha256": hashlib.sha256(query.encode("utf-8")).hexdigest(),
        "corpus_sha256": corpus_sha,
        "runtime": runtime,
        "evidence_cards": cards,
        "sibling_diagnostic": sibling_diagnostic(cards, documents),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evidence-first local ATT&CK retrieval demo")
    parser.add_argument(
        "--query",
        required=True,
        help="Analyst-supplied text; it is embedded locally and not written to project output.",
    )
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()
    if args.top_k < 1 or args.top_k > 20:
        raise ValueError("top-k must be between 1 and 20")
    output = {
        **retrieve(args.query, args.top_k),
        "run": "ragscope-local-evidence-demo-v0",
        "query_text_persisted": False,
        "limitations": [
            "Retrieved definitions are evidence cards, not an incident verdict or automated CTI classification.",
            "No generation is used; the user must inspect cited ATT&CK definitions.",
            "SAGE M3 is disabled because its controlled dev calibration did not meet the declared risk bound.",
        ],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
