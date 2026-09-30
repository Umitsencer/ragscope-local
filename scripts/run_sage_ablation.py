"""Controlled SAGE-ATT&CK ablation with dev-only parameter selection.

SAGE is evaluated only on the definition-only MITRE procedure benchmark.  It
does not claim independent report generalization or a new embedding model.
The dense top result chooses a candidate ATT&CK family; within that family,
the method combines sibling-local dense and BM25 evidence.  A dev-calibrated
gate emits ``child``, ``parent`` or ``abstain`` and records every decision.
"""

from __future__ import annotations

import argparse
import collections
import json
import math
from pathlib import Path

import numpy as np
from audit_sources import ROOT, sha256
from build_foundry_embedding_cache import cache_path
from run_bm25_baseline import (
    BENCHMARK_PATH,
    CORPUS_PATH,
    build_bm25,
    parent_mapping,
    read_jsonl,
    tokens,
)

OUTPUT_DIR = ROOT / "data/evaluation"
RISK_BUDGET = 0.20
CONFIDENCE = 0.95
ALPHAS = (0.0, 0.25, 0.5, 1.0)
QUANTILES = (0.0, 0.10, 0.25, 0.50, 0.75)


def cached_vectors(path: Path, expected_source_sha256: str) -> dict[str, list[float]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise ValueError(f"Empty embedding cache: {path}")
    header = json.loads(lines[0])
    if header.get("kind") != "header" or header.get("source_sha256") != expected_source_sha256:
        raise ValueError(f"Embedding cache provenance mismatch: {path}")
    rows = [json.loads(line) for line in lines[1:] if line.strip()]
    vectors = {row["record_id"]: row["vector"] for row in rows}
    if len(vectors) != len(rows):
        raise ValueError(f"Duplicate record IDs in embedding cache: {path}")
    return vectors


def bm25_scores(index: dict, query: str) -> dict[str, float]:
    """Return deterministic raw BM25 scores for sibling-local comparison."""
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
    return scores


def zscore(values: np.ndarray) -> np.ndarray:
    deviation = float(values.std())
    if deviation == 0.0:
        return np.zeros_like(values)
    return (values - float(values.mean())) / deviation


def quantile(values: list[float], value: float) -> float:
    if not values:
        raise ValueError("Cannot calculate a quantile of no values")
    return float(np.quantile(np.asarray(values, dtype=np.float64), value, method="linear"))


def binomial_cdf(errors: int, trials: int, probability: float) -> float:
    if errors < 0 or errors > trials:
        raise ValueError("Invalid binomial parameters")
    if probability <= 0.0:
        return 1.0
    if probability >= 1.0:
        return 1.0 if errors == trials else 0.0
    log_terms = [
        math.lgamma(trials + 1)
        - math.lgamma(successes + 1)
        - math.lgamma(trials - successes + 1)
        + successes * math.log(probability)
        + (trials - successes) * math.log1p(-probability)
        for successes in range(errors + 1)
    ]
    maximum = max(log_terms)
    return math.exp(maximum) * sum(math.exp(term - maximum) for term in log_terms)


def clopper_pearson_upper(errors: int, trials: int, confidence: float = CONFIDENCE) -> float:
    """One-sided exact binomial upper bound without an undeclared SciPy dependency."""
    if trials == 0 or errors == trials:
        return 1.0
    alpha = 1.0 - confidence
    low, high = 0.0, 1.0
    for _ in range(80):
        midpoint = (low + high) / 2.0
        if binomial_cdf(errors, trials, midpoint) > alpha:
            low = midpoint
        else:
            high = midpoint
    return high


def build_features(
    records: list[dict],
    documents: list[dict],
    document_vectors: dict[str, list[float]],
    query_vectors: dict[str, list[float]],
) -> list[dict]:
    """Build family-local features without changing any model or tokenizer."""
    document_ids = sorted(document_vectors)
    matrix = np.asarray([document_vectors[item] for item in document_ids], dtype=np.float32)
    index = build_bm25(documents)
    parents = parent_mapping(documents)
    children_by_parent: dict[str, list[str]] = collections.defaultdict(list)
    for child, parent in parents.items():
        children_by_parent[parent].append(child)
    for children in children_by_parent.values():
        children.sort()
    features = []
    for record in records:
        query_id = record["query_id"]
        dense_values = matrix @ np.asarray(query_vectors[query_id], dtype=np.float32)
        best_position = int(np.argmax(dense_values))
        dense_top = document_ids[best_position]
        family_parent = parents.get(dense_top, dense_top)
        siblings = children_by_parent.get(family_parent, [])
        sibling_supported = len(siblings) >= 2 and dense_top in parents
        item = {
            "query_id": query_id,
            "gold_ids": sorted(record["valid_target_ids"]),
            "dense_top": dense_top,
            "dense_top_score": float(dense_values[best_position]),
            "family_parent": family_parent,
            "sibling_supported": sibling_supported,
        }
        if sibling_supported:
            sibling_positions = [document_ids.index(sibling) for sibling in siblings]
            dense_siblings = dense_values[sibling_positions].astype(np.float64)
            sparse = bm25_scores(index, record["query_text"])
            sparse_siblings = np.asarray(
                [sparse[sibling] for sibling in siblings], dtype=np.float64
            )
            item.update(
                {
                    "siblings": siblings,
                    "dense_z": zscore(dense_siblings).tolist(),
                    "bm25_z": zscore(sparse_siblings).tolist(),
                }
            )
        features.append(item)
    return features


def decide(feature: dict, alpha: float, margin_threshold: float, score_threshold: float) -> dict:
    """Return a traceable child/parent/abstain decision for one query."""
    if not feature["sibling_supported"]:
        return {
            **feature,
            "output_id": feature["dense_top"],
            "decision": "dense_passthrough",
            "reason": "no_sibling_family",
            "margin": None,
        }
    combined = np.asarray(feature["dense_z"], dtype=np.float64) + alpha * np.asarray(
        feature["bm25_z"], dtype=np.float64
    )
    ordered = sorted(
        range(len(feature["siblings"])),
        key=lambda position: (-combined[position], feature["siblings"][position]),
    )
    winner, runner_up = ordered[0], ordered[1]
    margin = float(combined[winner] - combined[runner_up])
    if feature["dense_top_score"] < score_threshold:
        output_id, decision, reason = None, "abstain", "low_global_dense_similarity"
    elif margin < margin_threshold:
        output_id, decision, reason = (
            feature["family_parent"],
            "parent",
            "insufficient_sibling_margin",
        )
    else:
        output_id, decision, reason = feature["siblings"][winner], "child", "sibling_margin_passed"
    return {
        **feature,
        "output_id": output_id,
        "decision": decision,
        "reason": reason,
        "margin": margin,
        "runner_up_id": feature["siblings"][runner_up],
        "winner_dense_z": float(feature["dense_z"][winner]),
        "winner_bm25_z": float(feature["bm25_z"][winner]),
    }


def evaluate(
    features: list[dict], alpha: float, margin_threshold: float, score_threshold: float
) -> dict:
    traces = [decide(feature, alpha, margin_threshold, score_threshold) for feature in features]
    eligible = [trace for trace in traces if trace["sibling_supported"]]
    child = [trace for trace in eligible if trace["decision"] == "child"]
    child_correct = sum(trace["output_id"] in trace["gold_ids"] for trace in child)
    dense_correct = sum(trace["dense_top"] in trace["gold_ids"] for trace in eligible)
    errors = len(child) - child_correct
    return {
        "eligible_queries": len(eligible),
        "child_decisions": len(child),
        "parent_backoffs": sum(trace["decision"] == "parent" for trace in eligible),
        "abstentions": sum(trace["decision"] == "abstain" for trace in eligible),
        "child_coverage": len(child) / len(eligible) if eligible else 0.0,
        "selective_child_accuracy": child_correct / len(child) if child else None,
        "selective_child_error": errors / len(child) if child else None,
        "clopper_pearson_error_upper_95": clopper_pearson_upper(errors, len(child))
        if child
        else 1.0,
        "dense_top_exact_accuracy_on_eligible": dense_correct / len(eligible) if eligible else None,
        "traces": traces,
    }


def select_config(features: list[dict]) -> tuple[dict, dict]:
    """Choose parameters only from dev data under a declared, provisional risk budget."""
    provisional = []
    for alpha in ALPHAS:
        unfiltered = [
            decide(feature, alpha, 0.0, -1.0)
            for feature in features
            if feature["sibling_supported"]
        ]
        margins = [trace["margin"] for trace in unfiltered]
        scores = [trace["dense_top_score"] for trace in unfiltered]
        for margin_quantile in QUANTILES:
            for score_quantile in QUANTILES:
                metrics = evaluate(
                    features,
                    alpha,
                    quantile(margins, margin_quantile),
                    quantile(scores, score_quantile),
                )
                provisional.append(
                    {
                        "alpha": alpha,
                        "margin_quantile": margin_quantile,
                        "score_quantile": score_quantile,
                        **{key: value for key, value in metrics.items() if key != "traces"},
                    }
                )
    accepted = [
        item
        for item in provisional
        if item["child_decisions"] and item["clopper_pearson_error_upper_95"] <= RISK_BUDGET
    ]
    if not accepted:
        closest = min(
            provisional,
            key=lambda item: (item["clopper_pearson_error_upper_95"], -item["child_coverage"]),
        )
        return None, {
            "status": "blocked",
            "risk_budget": RISK_BUDGET,
            "confidence": CONFIDENCE,
            "candidates": provisional,
            "closest_candidate": closest,
        }
    winner = max(
        accepted,
        key=lambda item: (
            item["child_coverage"],
            item["selective_child_accuracy"],
            -item["alpha"],
            -item["margin_quantile"],
            -item["score_quantile"],
        ),
    )
    config = {key: winner[key] for key in ("alpha", "margin_quantile", "score_quantile")}
    return config, {
        "status": "passed",
        "risk_budget": RISK_BUDGET,
        "confidence": CONFIDENCE,
        "candidates": provisional,
        "selected": winner,
    }


def select_ranking_config(features: list[dict]) -> tuple[dict, dict]:
    """Select only M1+M2 sibling reranking; it deliberately has no risk gate."""
    candidates = []
    for alpha in ALPHAS:
        metrics = evaluate(features, alpha, -1_000_000_000.0, -1_000_000_000.0)
        candidates.append(
            {"alpha": alpha, **{key: value for key, value in metrics.items() if key != "traces"}}
        )
    winner = max(candidates, key=lambda item: (item["selective_child_accuracy"], -item["alpha"]))
    return {
        "alpha": winner["alpha"],
        "margin_threshold": -1_000_000_000.0,
        "score_threshold": -1_000_000_000.0,
    }, {"candidates": candidates, "selected": winner}


def validate_frozen_config(artifact: dict, mode: str, corpus_sha: str, benchmark_sha: str) -> dict:
    """Reject configs from another dataset, split or selection procedure."""
    expected_run = (
        "sage-attack-ranking-dev-selection-v0"
        if mode == "ranking-evaluate"
        else "sage-attack-dev-selection-v0"
    )
    if artifact.get("run") != expected_run or artifact.get("split") != "dev":
        raise ValueError("Expected matching dev selection artifact")
    if artifact.get("test_split_accessed") is not False:
        raise ValueError("Selection must declare no test access")
    if (
        artifact.get("corpus_sha256") != corpus_sha
        or artifact.get("benchmark_sha256") != benchmark_sha
    ):
        raise ValueError("Frozen config dataset hash mismatch")
    if mode == "evaluate" and artifact.get("status") != "passed":
        raise ValueError("M3 selection gate did not pass")
    config = artifact.get("selected_config")
    if not isinstance(config, dict):
        raise ValueError("Missing frozen config")
    for key in ("alpha", "margin_threshold", "score_threshold"):
        value = config.get(key)
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise ValueError(f"Invalid frozen config value: {key}")
    if config["alpha"] not in ALPHAS:
        raise ValueError("Unknown lexical weight")
    return config


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=("select", "evaluate", "ranking-select", "ranking-evaluate"),
        required=True,
    )
    parser.add_argument("--split", choices=("dev", "test"), required=True)
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    if args.mode in ("select", "ranking-select") and args.split != "dev":
        raise ValueError("SAGE parameter selection is allowed only on the dev split")
    if args.mode in ("evaluate", "ranking-evaluate") and args.config is None:
        raise ValueError("Evaluation requires a frozen config produced on dev")
    documents = read_jsonl(CORPUS_PATH)
    corpus_sha = sha256(CORPUS_PATH)
    benchmark_sha = sha256(BENCHMARK_PATH)
    frozen = None
    if args.mode in ("evaluate", "ranking-evaluate"):
        frozen = validate_frozen_config(
            json.loads(args.config.read_text(encoding="utf-8")),
            args.mode,
            corpus_sha,
            benchmark_sha,
        )
    records = [record for record in read_jsonl(BENCHMARK_PATH) if record["split"] == args.split]
    document_vectors = cached_vectors(cache_path("corpus", None), corpus_sha)
    query_vectors = cached_vectors(cache_path("queries", args.split), benchmark_sha)
    if set(document_vectors) != {document["document_id"] for document in documents}:
        raise ValueError("Corpus cache IDs do not match the definition corpus")
    if set(query_vectors) != {record["query_id"] for record in records}:
        raise ValueError("Query cache IDs do not match the requested split")
    features = build_features(records, documents, document_vectors, query_vectors)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if args.mode == "select":
        config, selection = select_config(features)
        if config is not None:
            alpha = config["alpha"]
            raw = [
                decide(feature, alpha, 0.0, -1.0)
                for feature in features
                if feature["sibling_supported"]
            ]
            selection["selected_config"] = {
                **config,
                "margin_threshold": quantile(
                    [item["margin"] for item in raw], config["margin_quantile"]
                ),
                "score_threshold": quantile(
                    [item["dense_top_score"] for item in raw], config["score_quantile"]
                ),
            }
        output = {
            "run": "sage-attack-dev-selection-v0",
            "split": "dev",
            "test_split_accessed": False,
            "corpus_sha256": corpus_sha,
            "benchmark_sha256": benchmark_sha,
            **selection,
        }
        path = OUTPUT_DIR / "sage_attack_dev_selection.json"
    elif args.mode == "ranking-select":
        config, selection = select_ranking_config(features)
        output = {
            "run": "sage-attack-ranking-dev-selection-v0",
            "split": "dev",
            "test_split_accessed": False,
            "corpus_sha256": corpus_sha,
            "benchmark_sha256": benchmark_sha,
            "selected_config": config,
            **selection,
        }
        path = OUTPUT_DIR / "sage_attack_ranking_dev_selection.json"
    else:
        metrics = evaluate(
            features, frozen["alpha"], frozen["margin_threshold"], frozen["score_threshold"]
        )
        is_ranking_only = args.mode == "ranking-evaluate"
        output = {
            "run": "sage-attack-ranking-controlled-ablation-v0"
            if is_ranking_only
            else "sage-attack-controlled-ablation-v0",
            "split": args.split,
            "config_path": str(args.config),
            "frozen_config": frozen,
            "corpus_sha256": corpus_sha,
            "benchmark_sha256": benchmark_sha,
            "limitations": [
                "Controlled MITRE benchmark only; not independent report performance.",
                "This is M1+M2 sibling reranking without a calibrated child/parent/abstain safety claim."
                if is_ranking_only
                else "Risk bound concerns accepted child decisions under this dev-selected protocol; it is not an operational safety guarantee.",
                "Parent backoff and abstention have no independent human gold label in this benchmark.",
            ],
            **metrics,
        }
        path = OUTPUT_DIR / (
            f"sage_attack_ranking_controlled_{args.split}.json"
            if is_ranking_only
            else f"sage_attack_controlled_{args.split}.json"
        )
    path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"SAGE artifact written: {path}")


if __name__ == "__main__":
    main()
