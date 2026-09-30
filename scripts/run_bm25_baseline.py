"""Run a dependency-free BM25 baseline on the controlled MITRE benchmark.

Usage: python -B scripts/run_bm25_baseline.py --split test
The output contains metrics and label-level diagnostics, never query text.
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import re
from pathlib import Path

from audit_sources import ROOT, sha256

CORPUS_PATH = ROOT / "data/derived/mitre_definition_corpus.jsonl"
BENCHMARK_PATH = ROOT / "data/derived/mitre_procedure_benchmark.jsonl"
OUTPUT_DIR = ROOT / "data/evaluation"
TOKEN_RE = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?", re.IGNORECASE)


def tokens(text: str) -> list[str]:
    return TOKEN_RE.findall(text.casefold())


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def build_bm25(documents: list[dict], k1: float = 1.2, b: float = 0.75) -> dict:
    """Build a small deterministic in-memory BM25 index."""
    if not documents:
        raise ValueError("Cannot build BM25 index for an empty corpus")
    doc_tokens = {
        document["document_id"]: tokens(document["name"] + " " + document["description"])
        for document in documents
    }
    lengths = {document_id: len(values) for document_id, values in doc_tokens.items()}
    if any(length == 0 for length in lengths.values()):
        raise ValueError("Empty document after tokenization")
    postings: dict[str, dict[str, int]] = collections.defaultdict(dict)
    for document_id, values in doc_tokens.items():
        for term, count in collections.Counter(values).items():
            postings[term][document_id] = count
    return {
        "document_ids": sorted(doc_tokens),
        "postings": postings,
        "lengths": lengths,
        "avg_length": sum(lengths.values()) / len(lengths),
        "k1": k1,
        "b": b,
    }


def rank(index: dict, query: str) -> list[str]:
    scores: dict[str, float] = collections.defaultdict(float)
    total_documents = len(index["document_ids"])
    for term in tokens(query):
        posting = index["postings"].get(term)
        if not posting:
            continue
        document_frequency = len(posting)
        inverse_document_frequency = math.log(
            1 + (total_documents - document_frequency + 0.5) / (document_frequency + 0.5)
        )
        for document_id, frequency in posting.items():
            length_normalizer = index["k1"] * (
                1 - index["b"] + index["b"] * index["lengths"][document_id] / index["avg_length"]
            )
            scores[document_id] += (
                inverse_document_frequency
                * frequency
                * (index["k1"] + 1)
                / (frequency + length_normalizer)
            )
    return sorted(
        index["document_ids"], key=lambda document_id: (-scores[document_id], document_id)
    )


def evaluate(
    records: list[dict],
    index: dict,
    parent_by_child: dict[str, str],
    cutoffs: tuple[int, ...] = (1, 3, 5, 10),
) -> dict:
    """Calculate query-macro multi-label retrieval metrics and family diagnostics."""
    if not records:
        raise ValueError("No benchmark records selected")
    metrics = {f"hit_at_{cutoff}": 0 for cutoff in cutoffs}
    metrics.update({f"recall_at_{cutoff}": 0.0 for cutoff in cutoffs})
    reciprocal_rank_sum = 0.0
    family = collections.defaultdict(
        lambda: {"queries": 0, "hit_at_10": 0, "reciprocal_rank_sum": 0.0}
    )
    for record in records:
        gold = set(record["valid_target_ids"])
        ranking = rank(index, record["query_text"])
        rank_by_id = {
            document_id: position for position, document_id in enumerate(ranking, start=1)
        }
        best_rank = min(rank_by_id[target] for target in gold)
        reciprocal_rank = 1.0 / best_rank
        reciprocal_rank_sum += reciprocal_rank
        for cutoff in cutoffs:
            retrieved = set(ranking[:cutoff])
            metrics[f"hit_at_{cutoff}"] += bool(gold & retrieved)
            metrics[f"recall_at_{cutoff}"] += len(gold & retrieved) / len(gold)
        child_targets = [target for target in gold if target in parent_by_child]
        if child_targets:
            # A multi-label query may touch several families; report it under each.
            for parent in sorted({parent_by_child[target] for target in child_targets}):
                family[parent]["queries"] += 1
                family[parent]["hit_at_10"] += bool(gold & set(ranking[:10]))
                family[parent]["reciprocal_rank_sum"] += reciprocal_rank
    count = len(records)
    average = {key: value / count for key, value in metrics.items()}
    average["mrr"] = reciprocal_rank_sum / count
    family_metrics = {
        parent: {
            "queries": value["queries"],
            "hit_at_10": value["hit_at_10"] / value["queries"],
            "mrr": value["reciprocal_rank_sum"] / value["queries"],
        }
        for parent, value in sorted(family.items())
    }
    return {
        "queries": count,
        "query_macro_metrics": average,
        "subtechnique_family_metrics": family_metrics,
    }


def parent_mapping(documents: list[dict]) -> dict[str, str]:
    return {
        document["document_id"]: document["parent_technique_id"]
        for document in documents
        if document["parent_technique_id"] is not None
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("train", "dev", "test"), default="test")
    args = parser.parse_args()
    documents = read_jsonl(CORPUS_PATH)
    records = [record for record in read_jsonl(BENCHMARK_PATH) if record["split"] == args.split]
    index = build_bm25(documents)
    result = evaluate(records, index, parent_mapping(documents))
    output = {
        "run": "bm25-definition-only-v1",
        "split": args.split,
        "corpus_sha256": sha256(CORPUS_PATH),
        "benchmark_sha256": sha256(BENCHMARK_PATH),
        "configuration": {
            "tokenizer": TOKEN_RE.pattern,
            "k1": index["k1"],
            "b": index["b"],
            "ranking_tie_break": "document_id ascending",
        },
        "limitations": [
            "Controlled MITRE procedure-retrieval result only; it is not independent real-report performance.",
            "This is a sparse lexical baseline, not a Foundry Local embedding or SAGE result.",
            "Family metrics include child-labeled queries and should not be interpreted without their query counts.",
        ],
        **result,
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"bm25_definition_only_{args.split}.json"
    output_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Evaluation written: {output_path}")
    print(
        f"{args.split} queries: {result['queries']}; MRR: {result['query_macro_metrics']['mrr']:.6f}; Hit@10: {result['query_macro_metrics']['hit_at_10']:.6f}"
    )


if __name__ == "__main__":
    main()
