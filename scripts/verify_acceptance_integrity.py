"""Verify fixed-case acceptance artifacts without making semantic claims."""

import argparse
import hashlib
import json
from pathlib import Path

from audit_sources import ROOT

APPLICATION_FILES = (
    "scripts/demo_local_rag.py",
    "scripts/demo_local_extractive.py",
    "scripts/demo_local_retrieval.py",
    "scripts/run_rag_acceptance.py",
    "src/ragscope/foundry.py",
    "src/ragscope/security.py",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def portable_text_digests(path: Path) -> set[str]:
    """Compute sha256 digests for both canonical LF and CRLF encodings of UTF-8 text.

    Security boundary: This normalization permits checkout portability across platforms
    (e.g., Windows CRLF working tree vs. Linux/git checkout LF) without permitting any
    semantic or content change. It is strictly limited to newline normalization equivalence
    and is not a general hash bypass.
    """
    text = path.read_text(encoding="utf-8")
    canonical_lf = text.replace("\r\n", "\n").replace("\r", "\n")
    canonical_crlf = canonical_lf.replace("\n", "\r\n")
    return {
        hashlib.sha256(canonical_lf.encode("utf-8")).hexdigest(),
        hashlib.sha256(canonical_crlf.encode("utf-8")).hexdigest(),
    }


def verify(run_dir: Path) -> dict:
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    cases_doc = json.loads((ROOT / "data/acceptance/cases.json").read_text(encoding="utf-8"))
    expected_cases = cases_doc["cases"]
    corpus_path = ROOT / "data/derived/mitre_definition_corpus.jsonl"
    corpus = {
        row["document_id"]: row
        for row in (
            json.loads(line)
            for line in corpus_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    }
    errors, quote_count = [], 0
    expected_ids = [case["id"] for case in expected_cases]
    if summary.get("case_count") != len(expected_ids) or summary.get("completed_cases") != len(
        expected_ids
    ):
        errors.append("summary_case_count")
    if summary.get("process_ok_count") != len(expected_ids):
        errors.append("summary_process_count")
    if summary.get("cases_sha256") != digest(ROOT / "data/acceptance/cases.json"):
        errors.append("case_manifest_hash")
    manifest = summary.get("script_sha256", {})
    if set(manifest) != set(APPLICATION_FILES):
        errors.append("application_manifest_scope")
    for relative_path in APPLICATION_FILES:
        path = ROOT / relative_path
        if not path.is_file() or digest(path) != manifest.get(relative_path):
            errors.append(f"script_hash:{relative_path}")
    outcomes = {}
    for index, expected_case in enumerate(expected_cases, 1):
        record = json.loads((run_dir / f"case-{index:02d}.json").read_text(encoding="utf-8"))
        if record.get("id") != expected_case["id"] or not record.get("process_ok"):
            errors.append(f"case_identity_or_process:{index}")
            continue
        output = record.get("output", {})
        if (
            output.get("query_sha256")
            != hashlib.sha256(expected_case["query"].encode("utf-8")).hexdigest()
        ):
            errors.append(f"query_hash:{record['id']}")
        if output.get("corpus_sha256") not in portable_text_digests(corpus_path):
            errors.append(f"corpus_hash:{record['id']}")
        cards = {card["attack_id"]: card for card in output.get("evidence_cards", [])}
        for quote in output.get("generation", {}).get("quotes", []):
            quote_count += 1
            card = cards.get(quote.get("attack_id"))
            source = corpus.get(quote.get("attack_id"))
            start, end = quote.get("start"), quote.get("end")
            if not card or not source or not isinstance(start, int) or not isinstance(end, int):
                errors.append(f"quote_reference:{record['id']}")
                continue
            definition = source["description"]
            expected_hash = hashlib.sha256(definition.encode("utf-8")).hexdigest()
            if (
                card.get("definition") != definition
                or not 0 <= start < end <= len(definition)
                or definition[start:end] != quote.get("quote")
                or quote.get("source_sha256") != expected_hash
                or quote.get("exact_source_match") is not True
            ):
                errors.append(f"quote_integrity:{record['id']}:{quote.get('span_id')}")
        outcomes[record["id"]] = record.get("outcome")
    if list(outcomes) != expected_ids:
        errors.append("case_order")
    runner_expected = summary.get("script_sha256", {}).get("scripts/run_rag_acceptance.py")
    runner_current = digest(ROOT / "scripts/run_rag_acceptance.py")
    return {
        "run": "acceptance-integrity-v1",
        "acceptance_directory": run_dir.name,
        "integrity_passed": not errors,
        "errors": errors,
        "cases_checked": len(outcomes),
        "quotes_checked": quote_count,
        "outcomes": outcomes,
        "orchestration_script_manifest_match": runner_expected == runner_current,
        "orchestration_note": (
            "The orchestration script no longer matches this preserved run manifest."
            if runner_expected != runner_current
            else None
        ),
        "application_file_sha256": {name: digest(ROOT / name) for name in APPLICATION_FILES},
        "semantic_review": "separate_human_or_assistant_review_required",
        "independent_gold": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run_dir, output = args.run_dir.resolve(), args.output.resolve()
    allowed = (ROOT / "data/acceptance").resolve()
    if not run_dir.is_relative_to(allowed) or not output.is_relative_to(run_dir):
        parser.error("Run and output must stay under the selected acceptance directory")
    report = verify(run_dir)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    if not report["integrity_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
