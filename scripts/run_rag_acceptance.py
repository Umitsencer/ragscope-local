"""Run fixed synthetic RAG examples with per-case timeouts and preserved failures.

This writes functional evidence, never gold labels or benchmark superiority claims.
Use a new output directory for every run; existing results are never overwritten.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

from audit_sources import ROOT

from ragscope.security import validate_query

CASES_PATH = ROOT / "data/acceptance/cases.json"
MANIFEST_FILES = (
    "scripts/demo_local_rag.py",
    "scripts/demo_local_extractive.py",
    "scripts/demo_local_retrieval.py",
    "scripts/run_rag_acceptance.py",
    "src/ragscope/foundry.py",
    "src/ragscope/security.py",
)


def load_cases(path: Path) -> list[dict]:
    cases = json.loads(path.read_text(encoding="utf-8"))["cases"]
    ids = [row["id"] for row in cases]
    if not cases or len(ids) != len(set(ids)):
        raise ValueError("Empty or duplicate acceptance cases")
    for row in cases:
        validate_query(row["query"])
    return cases


def assess_process(returncode: int, stdout: str, mode: str = "freeform") -> dict:
    if returncode != 0:
        return {"process_ok": False, "outcome": "process_error", "semantic_review": "pending"}
    try:
        output = json.loads(stdout)
        expected_run = (
            "ragscope-local-extractive-demo-v1"
            if mode == "extractive"
            else "ragscope-local-rag-demo-v0"
        )
        if output.get("run") != expected_run:
            raise ValueError("Unexpected run")
        status = output["generation"]["status"]
        allowed = (
            ("evidence_selected", "insufficient_evidence", "rejected_output")
            if mode == "extractive"
            else ("answer", "insufficient_evidence", "rejected_output")
        )
        if status not in allowed:
            raise ValueError("Unknown status")
        return {
            "process_ok": True,
            "outcome": status,
            "semantic_review": "pending",
            "output": output,
        }
    except (ValueError, KeyError, TypeError, AttributeError):
        return {"process_ok": False, "outcome": "invalid_output", "semantic_review": "pending"}


def run_case(case: dict, model_id: str, timeout: int, mode: str = "freeform") -> dict:
    started = time.perf_counter()
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        script = "demo_local_extractive.py" if mode == "extractive" else "demo_local_rag.py"
        command = [
            sys.executable,
            "-B",
            str(ROOT / "scripts" / script),
            "--generation-model",
            model_id,
            "--query",
            case["query"],
            "--top-k",
            "3",
        ]
        if mode == "freeform":
            command.append("--allow-experimental-generation")
        process = subprocess.run(
            command,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            cwd=ROOT,
            timeout=timeout,
            check=False,
        )
        assessment = assess_process(process.returncode, process.stdout, mode)
        return {
            "id": case["id"],
            "review_focus": case["review_focus"],
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "exit_code": process.returncode,
            "stderr": process.stderr.replace(str(ROOT), "<PROJECT_ROOT>").replace(
                sys.prefix, "<PYTHON_ENV>"
            ),
            "unparsed_stdout": process.stdout if not assessment["process_ok"] else "",
            **assessment,
        }
    except subprocess.TimeoutExpired:
        return {
            "id": case["id"],
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "exit_code": None,
            "process_ok": False,
            "outcome": "timeout",
            "semantic_review": "pending",
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generation-model", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--mode", choices=("freeform", "extractive"), default="freeform")
    args = parser.parse_args()
    if not 1 <= args.timeout <= 600:
        parser.error("timeout must be 1–600 seconds")
    cases = load_cases(CASES_PATH)
    output_dir = args.output_dir.resolve()
    allowed = (ROOT / "data/acceptance").resolve()
    if output_dir == allowed or not output_dir.is_relative_to(allowed):
        parser.error("output-dir must be a new subdirectory of data/acceptance")
    output_dir.mkdir(parents=True, exist_ok=False)
    results = []
    script_hashes = {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in MANIFEST_FILES
    }
    for index, case in enumerate(cases, 1):
        print(f"Starting {index}/{len(cases)}: {case['id']}", flush=True)
        result = run_case(case, args.generation_model, args.timeout, args.mode)
        results.append(result)
        (output_dir / f"case-{index:02d}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(
            f"Finished {case['id']}: {result['outcome']} ({result['elapsed_seconds']}s)", flush=True
        )
    summary = {
        "run": "synthetic-rag-acceptance-v1",
        "generation_model_requested": args.generation_model,
        "mode": args.mode,
        "python_version": platform.python_version(),
        "dependencies": {
            name: importlib.metadata.version(name)
            for name in ("numpy", "foundry-local-sdk", "openai", "pydantic")
        },
        "script_sha256": script_hashes,
        "cases_sha256": hashlib.sha256(CASES_PATH.read_bytes()).hexdigest(),
        "case_count": len(cases),
        "completed_cases": len(results),
        "process_ok_count": sum(row["process_ok"] for row in results),
        "semantic_review": "pending",
        "independent_gold": False,
        "outcomes": {row["id"]: row["outcome"] for row in results},
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    if not all(row["process_ok"] for row in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
