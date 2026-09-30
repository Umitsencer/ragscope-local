"""Analyze the frozen SAGE M1+M2 test trace without tuning it further."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from audit_sources import ROOT

DEFAULT_INPUT = ROOT / "data/evaluation/sage_attack_ranking_controlled_test.json"
DEFAULT_OUTPUT = ROOT / "data/evaluation/sage_attack_ranking_test_analysis.json"


def paired_bootstrap_delta(
    deltas: np.ndarray, replicates: int = 10_000, seed: int = 20260920
) -> dict:
    """Deterministic percentile CI for a paired binary-accuracy difference."""
    if deltas.ndim != 1 or len(deltas) == 0:
        raise ValueError("Expected a non-empty one-dimensional paired delta array")
    generator = np.random.default_rng(seed)
    samples = []
    for _ in range(replicates):
        indices = generator.integers(0, len(deltas), size=len(deltas))
        samples.append(float(deltas[indices].mean()))
    return {
        "observed_delta": float(deltas.mean()),
        "replicates": replicates,
        "seed": seed,
        "percentile_ci_95": [
            float(np.quantile(samples, 0.025)),
            float(np.quantile(samples, 0.975)),
        ],
    }


def analyze(traces: list[dict], minimum_family_queries: int = 20) -> dict:
    """Return paired and family-level diagnostics; no query text is emitted."""
    eligible_traces = [trace for trace in traces if trace.get("sibling_supported")]
    if not eligible_traces:
        raise ValueError("No sibling-supported SAGE traces found")
    dense = np.asarray(
        [trace["dense_top"] in trace["gold_ids"] for trace in eligible_traces], dtype=np.int8
    )
    sage = np.asarray(
        [trace["output_id"] in trace["gold_ids"] for trace in eligible_traces], dtype=np.int8
    )
    deltas = sage - dense
    family_rows = {}
    for trace, dense_correct, sage_correct in zip(eligible_traces, dense, sage, strict=True):
        group = family_rows.setdefault(trace["family_parent"], {"dense": [], "sage": []})
        group["dense"].append(int(dense_correct))
        group["sage"].append(int(sage_correct))
    family = []
    for parent, values in family_rows.items():
        query_count = len(values["dense"])
        if query_count >= minimum_family_queries:
            dense_accuracy = float(np.mean(values["dense"]))
            sage_accuracy = float(np.mean(values["sage"]))
            family.append(
                {
                    "parent_technique_id": parent,
                    "queries": query_count,
                    "dense_top_exact_accuracy": dense_accuracy,
                    "sage_exact_accuracy": sage_accuracy,
                    "delta": sage_accuracy - dense_accuracy,
                }
            )
    return {
        "eligible_queries": len(eligible_traces),
        "dense_only_correct": int(np.sum((dense == 1) & (sage == 0))),
        "sage_only_correct": int(np.sum((dense == 0) & (sage == 1))),
        "both_correct": int(np.sum((dense == 1) & (sage == 1))),
        "both_incorrect": int(np.sum((dense == 0) & (sage == 0))),
        "paired_bootstrap": paired_bootstrap_delta(deltas),
        "minimum_family_queries": minimum_family_queries,
        "family_slices": sorted(
            family, key=lambda item: (item["delta"], item["parent_technique_id"])
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--minimum-family-queries", type=int, default=20)
    args = parser.parse_args()
    if args.minimum_family_queries < 1:
        raise ValueError("minimum-family-queries must be positive")
    source = json.loads(args.input.read_text(encoding="utf-8"))
    if (
        source.get("run") != "sage-attack-ranking-controlled-ablation-v0"
        or source.get("split") != "test"
    ):
        raise ValueError("Input must be the frozen SAGE M1+M2 test artifact")
    output = {
        "run": "sage-attack-ranking-test-analysis-v0",
        "source_artifact": str(args.input),
        "limitations": [
            "Paired bootstrap quantifies uncertainty on this controlled sibling-supported test subset only.",
            "Family slices below the minimum query count are excluded from the table, not evidence of no effect.",
            "The analysis does not retune SAGE or establish independent-report generalization.",
        ],
        **analyze(source["traces"], args.minimum_family_queries),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"SAGE analysis written: {args.output}")
    print(
        f"Observed delta: {output['paired_bootstrap']['observed_delta']:.6f}; CI: {output['paired_bootstrap']['percentile_ci_95']}"
    )


if __name__ == "__main__":
    main()
