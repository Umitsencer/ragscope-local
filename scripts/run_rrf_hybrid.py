"""Evaluate BM25 + cached Foundry dense rankings using deterministic RRF."""

from __future__ import annotations

import argparse
import collections
import json

import numpy as np
from audit_sources import ROOT, sha256
from build_foundry_embedding_cache import cache_path
from run_bm25_baseline import (
    BENCHMARK_PATH,
    CORPUS_PATH,
    build_bm25,
    parent_mapping,
    rank,
    read_jsonl,
)

OUTPUT_DIR = ROOT / "data/evaluation"


def vectors(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or json.loads(lines[0]).get("kind") != "header":
        raise ValueError(f"Invalid cache: {path}")
    return {
        row["record_id"]: row["vector"]
        for row in (json.loads(line) for line in lines[1:] if line.strip())
    }


def rrf(bm25_ranking: list[str], dense_ranking: list[str], k: int) -> list[str]:
    scores = {}
    for ranking in (bm25_ranking, dense_ranking):
        for position, document_id in enumerate(ranking, start=1):
            scores[document_id] = scores.get(document_id, 0.0) + 1.0 / (k + position)
    return sorted(scores, key=lambda document_id: (-scores[document_id], document_id))


def component_rankings(
    records: list[dict],
    index: dict,
    document_vectors: dict[str, list[float]],
    query_vectors: dict[str, list[float]],
) -> dict[str, tuple[list[str], list[str]]]:
    """Compute sparse/dense ranks once; stable sort preserves ID tie-breaks."""
    document_ids = sorted(document_vectors)
    matrix = np.asarray(
        [document_vectors[document_id] for document_id in document_ids], dtype=np.float32
    )
    rankings = {}
    for record in records:
        dense_scores = matrix @ np.asarray(query_vectors[record["query_id"]], dtype=np.float32)
        dense = [document_ids[position] for position in np.argsort(-dense_scores, kind="stable")]
        rankings[record["query_id"]] = (rank(index, record["query_text"]), dense)
    return rankings


def evaluate_rrf(
    records: list[dict],
    parents: dict[str, str],
    components: dict[str, tuple[list[str], list[str]]],
    k: int,
) -> dict:
    """Evaluate RRF directly by record ID; no global ranking mutation."""
    cutoffs = (1, 3, 5, 10)
    totals = {f"hit_at_{cutoff}": 0 for cutoff in cutoffs}
    totals.update({f"recall_at_{cutoff}": 0.0 for cutoff in cutoffs})
    reciprocal_rank_sum = 0.0
    family = collections.defaultdict(
        lambda: {"queries": 0, "hit_at_10": 0, "reciprocal_rank_sum": 0.0}
    )
    for record in records:
        sparse, dense = components[record["query_id"]]
        ranking = rrf(sparse, dense, k)
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
        for parent in sorted({parents[target] for target in gold if target in parents}):
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
    parser.add_argument("--split", choices=("dev", "test"), required=True)
    parser.add_argument("--rrf-k", type=int, required=True)
    args = parser.parse_args()
    if args.rrf_k < 1:
        raise ValueError("rrf-k must be positive")
    documents = read_jsonl(CORPUS_PATH)
    document_vectors = vectors(cache_path("corpus", None))
    query_vectors = vectors(cache_path("queries", args.split))
    if set(document_vectors) != {document["document_id"] for document in documents}:
        raise ValueError("Corpus cache does not match corpus IDs")
    index = build_bm25(documents)
    records = [
        dict(record) for record in read_jsonl(BENCHMARK_PATH) if record["split"] == args.split
    ]
    components = component_rankings(records, index, document_vectors, query_vectors)
    result = evaluate_rrf(records, parent_mapping(documents), components, args.rrf_k)
    output = {
        "run": "rrf-bm25-foundry-dense-v1",
        "split": args.split,
        "rrf_k": args.rrf_k,
        "numpy_version": np.__version__,
        "corpus_sha256": sha256(CORPUS_PATH),
        "benchmark_sha256": sha256(BENCHMARK_PATH),
        "limitations": [
            "Controlled MITRE benchmark only.",
            "RRF k must be selected on dev, then frozen for test.",
        ],
        **result,
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"rrf_bm25_foundry_dense_{args.split}_k{args.rrf_k}.json"
    path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Evaluation written: {path}")
    print(
        f"MRR: {result['query_macro_metrics']['mrr']:.6f}; Hit@10: {result['query_macro_metrics']['hit_at_10']:.6f}"
    )


if __name__ == "__main__":
    main()
