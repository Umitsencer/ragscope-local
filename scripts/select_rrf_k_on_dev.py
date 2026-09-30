"""Pre-registered RRF selection: maximize dev MRR; ties choose lower k."""

from __future__ import annotations

import json

from audit_sources import ROOT, sha256
from build_foundry_embedding_cache import cache_path
from run_bm25_baseline import BENCHMARK_PATH, CORPUS_PATH, build_bm25, parent_mapping, read_jsonl
from run_rrf_hybrid import component_rankings, evaluate_rrf, vectors

CANDIDATE_K = (10, 20, 40, 60)


def main() -> None:
    documents = read_jsonl(CORPUS_PATH)
    corpus_vectors = vectors(cache_path("corpus", None))
    query_vectors = vectors(cache_path("queries", "dev"))
    records = [record for record in read_jsonl(BENCHMARK_PATH) if record["split"] == "dev"]
    index = build_bm25(documents)
    components = component_rankings(records, index, corpus_vectors, query_vectors)
    results = []
    for k in CANDIDATE_K:
        result = evaluate_rrf(records, parent_mapping(documents), components, k)
        results.append(
            {
                "rrf_k": k,
                "mrr": result["query_macro_metrics"]["mrr"],
                "hit_at_10": result["query_macro_metrics"]["hit_at_10"],
            }
        )
    winner = min(results, key=lambda value: (-value["mrr"], value["rrf_k"]))
    output = {
        "run": "rrf-k-selection-dev-v1",
        "selection_rule": "maximize dev query-macro MRR; ties choose lower rrf_k",
        "candidates": list(CANDIDATE_K),
        "selected_rrf_k": winner["rrf_k"],
        "results": results,
        "corpus_sha256": sha256(CORPUS_PATH),
        "benchmark_sha256": sha256(BENCHMARK_PATH),
        "test_split_accessed": False,
    }
    path = ROOT / "data/evaluation/rrf_k_selection_dev.json"
    path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Selected RRF k={winner['rrf_k']}; dev MRR={winner['mrr']:.6f}")


if __name__ == "__main__":
    main()
