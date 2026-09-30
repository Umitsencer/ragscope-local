"""Evaluate local Foundry embeddings on the controlled MITRE benchmark.

By default the selected model must already be in the local Foundry cache.  Use
``--allow-model-download`` only when deliberately authorizing a model download.

Usage: python -B scripts/run_foundry_dense_baseline.py --split test
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import time

from audit_sources import ROOT, sha256
from run_bm25_baseline import parent_mapping, read_jsonl

from ragscope.foundry import generate_embeddings, initialize_foundry, sdk_version

CORPUS_PATH = ROOT / "data/derived/mitre_definition_corpus.jsonl"
BENCHMARK_PATH = ROOT / "data/derived/mitre_procedure_benchmark.jsonl"
OUTPUT_DIR = ROOT / "data/evaluation"
MODEL_ALIAS = "qwen3-embedding-0.6b"


def normalize(vector: list[float]) -> list[float]:
    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude == 0:
        raise ValueError("Foundry returned a zero embedding vector")
    return [value / magnitude for value in vector]


def cosine_ranking(
    query_vector: list[float], document_vectors: dict[str, list[float]]
) -> list[str]:
    if not document_vectors:
        raise ValueError("Cannot rank against an empty document-vector index")
    return sorted(
        document_vectors,
        key=lambda document_id: (
            -sum(
                left * right
                for left, right in zip(query_vector, document_vectors[document_id], strict=True)
            ),
            document_id,
        ),
    )


def embed_in_batches(model, texts: list[str], batch_size: int) -> list[list[float]]:
    vectors: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        vectors.extend(
            normalize(vector)
            for vector in generate_embeddings(model, texts[start : start + batch_size])
        )
    return vectors


def evaluate(
    records: list[dict], document_vectors: dict[str, list[float]], parent_by_child: dict[str, str]
) -> dict:
    if not records:
        raise ValueError("No benchmark records selected")
    cutoffs = (1, 3, 5, 10)
    totals = {f"hit_at_{cutoff}": 0 for cutoff in cutoffs}
    totals.update({f"recall_at_{cutoff}": 0.0 for cutoff in cutoffs})
    reciprocal_rank_sum = 0.0
    family = collections.defaultdict(
        lambda: {"queries": 0, "hit_at_10": 0, "reciprocal_rank_sum": 0.0}
    )
    for record in records:
        ranking = cosine_ranking(record["query_vector"], document_vectors)
        gold = set(record["valid_target_ids"])
        rank_by_id = {
            document_id: position for position, document_id in enumerate(ranking, start=1)
        }
        best_rank = min(rank_by_id[target] for target in gold)
        reciprocal_rank = 1.0 / best_rank
        reciprocal_rank_sum += reciprocal_rank
        for cutoff in cutoffs:
            retrieved = set(ranking[:cutoff])
            totals[f"hit_at_{cutoff}"] += bool(gold & retrieved)
            totals[f"recall_at_{cutoff}"] += len(gold & retrieved) / len(gold)
        for parent in sorted(
            {parent_by_child[target] for target in gold if target in parent_by_child}
        ):
            family[parent]["queries"] += 1
            family[parent]["hit_at_10"] += bool(gold & set(ranking[:10]))
            family[parent]["reciprocal_rank_sum"] += reciprocal_rank
    count = len(records)
    metrics = {key: value / count for key, value in totals.items()}
    metrics["mrr"] = reciprocal_rank_sum / count
    return {
        "queries": count,
        "query_macro_metrics": metrics,
        "subtechnique_family_metrics": {
            parent: {
                "queries": value["queries"],
                "hit_at_10": value["hit_at_10"] / value["queries"],
                "mrr": value["reciprocal_rank_sum"] / value["queries"],
            }
            for parent, value in sorted(family.items())
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("train", "dev", "test"), default="test")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional first-N split records for smoke evaluation only.",
    )
    parser.add_argument(
        "--corpus-limit",
        type=int,
        default=None,
        help="Optional first-N corpus documents for smoke evaluation only.",
    )
    parser.add_argument("--allow-model-download", action="store_true")
    args = parser.parse_args()
    if args.batch_size < 1:
        raise ValueError("batch size must be positive")
    manager = initialize_foundry("ragscope_foundry_dense")
    model = manager.catalog.get_model(MODEL_ALIAS)
    if model is None:
        raise ValueError(f"Required catalog alias absent: {MODEL_ALIAS}")
    if not model.is_cached:
        if not args.allow_model_download:
            raise RuntimeError(
                "Model is not cached; rerun only with --allow-model-download after reviewing model metadata."
            )
        model.download()
    documents = read_jsonl(CORPUS_PATH)
    if args.corpus_limit is not None:
        documents = documents[: args.corpus_limit]
    document_ids = {document["document_id"] for document in documents}
    records = [
        record
        for record in read_jsonl(BENCHMARK_PATH)
        if record["split"] == args.split and set(record["valid_target_ids"]).issubset(document_ids)
    ]
    if args.limit is not None:
        records = records[: args.limit]
    started = time.perf_counter()
    try:
        model.load()
        document_vectors = dict(
            zip(
                [document["document_id"] for document in documents],
                embed_in_batches(
                    model,
                    [document["name"] + "\n" + document["description"] for document in documents],
                    args.batch_size,
                ),
                strict=True,
            )
        )
        query_vectors = embed_in_batches(
            model, [record["query_text"] for record in records], args.batch_size
        )
        for record, vector in zip(records, query_vectors, strict=True):
            record["query_vector"] = vector
        metrics = evaluate(records, document_vectors, parent_mapping(documents))
    finally:
        if model.is_loaded:
            model.unload()
    elapsed = time.perf_counter() - started
    output = {
        "run": "foundry-local-dense-definition-only-v1",
        "split": args.split,
        "sample_limit": args.limit,
        "corpus_document_limit": args.corpus_limit,
        "corpus_documents_evaluated": len(documents),
        "corpus_sha256": sha256(CORPUS_PATH),
        "benchmark_sha256": sha256(BENCHMARK_PATH),
        "model": {
            "alias": model.alias,
            "id": model.id,
            "catalog_version": model.info.version,
            "publisher": model.info.publisher,
            "license": model.info.license,
            "runtime_device": str(model.info.runtime.device_type),
            "execution_provider": model.info.runtime.execution_provider,
        },
        "sdk": {"package": "foundry-local-sdk", "version": sdk_version()},
        "configuration": {
            "batch_size": args.batch_size,
            "similarity": "cosine over L2-normalized embeddings",
            "ranking_tie_break": "document_id ascending",
        },
        "elapsed_seconds": elapsed,
        "limitations": [
            "Controlled MITRE procedure-retrieval result only; it is not independent real-report performance.",
            "A non-null sample_limit or corpus_document_limit denotes a smoke evaluation, not a benchmark result.",
            "CPU runtime and latency must be reported as measured, not generalized to GPU or NPU devices.",
        ],
        **metrics,
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = (f"_first{args.limit}" if args.limit is not None else "") + (
        f"_corpus{args.corpus_limit}" if args.corpus_limit is not None else ""
    )
    output_path = OUTPUT_DIR / f"foundry_dense_definition_only_{args.split}{suffix}.json"
    output_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Evaluation written: {output_path}")
    print(
        f"{args.split} queries: {metrics['queries']}; MRR: {metrics['query_macro_metrics']['mrr']:.6f}; elapsed seconds: {elapsed:.3f}"
    )


if __name__ == "__main__":
    main()
