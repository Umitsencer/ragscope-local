"""Build a controlled, source-grouped MITRE procedure-retrieval benchmark.

The benchmark is deliberately *not* an independent cyber-threat-report benchmark.
Queries are active ATT&CK ``uses`` relationship descriptions; labels are the active
Enterprise ATT&CK techniques targeted by those relationships.  Its purpose is a
reproducible controlled ablation of retrieval and granularity-selection methods.

Usage: python -B scripts/build_mitre_procedure_benchmark.py
Writes data/derived/mitre_procedure_benchmark.jsonl and companion audit/manifest.
"""

from __future__ import annotations

import collections
import hashlib
import json
import re

from audit_sources import ROOT, attack_mapping, sha256

SEED = "ragscope-mitre-procedure-v1-20260919"
RAW_PATH = ROOT / "data/raw/mitre/enterprise-attack-19.2.json"
OUTPUT_PATH = ROOT / "data/derived/mitre_procedure_benchmark.jsonl"
MANIFEST_PATH = ROOT / "data/derived/mitre_procedure_benchmark.manifest.json"
AUDIT_PATH = ROOT / "data/audit/mitre_procedure_benchmark_audit.json"


def canonical_text(text: str) -> str:
    """Normalize whitespace while preserving case for the retrieval query."""
    return re.sub(r"\s+", " ", text).strip()


def query_key(text: str) -> str:
    return hashlib.sha256(canonical_text(text).casefold().encode("utf-8")).hexdigest()


def split_for_source(source_ref: str, seed: str = SEED) -> str:
    """Stable 70/15/15 group split; source_ref is never shared across splits."""
    bucket = int(hashlib.sha256(f"{seed}:{source_ref}".encode()).hexdigest()[:8], 16) % 100
    return "train" if bucket < 70 else "dev" if bucket < 85 else "test"


def active_technique_mapping(objects: list[dict]) -> tuple[dict[str, str], dict[str, str]]:
    """Return active STIX-id→ATT&CK-id and active child→parent ATT&CK ids."""
    external, child_to_parent, _ = attack_mapping(objects)
    active_stix_to_external = {
        item["id"]: external_id
        for external_id, item in external.items()
        if not item.get("revoked") and not item.get("x_mitre_deprecated")
    }
    return active_stix_to_external, child_to_parent


def extract_relationship_rows(objects: list[dict]) -> list[dict]:
    """Extract non-empty active Enterprise technique ``uses`` descriptions."""
    active_stix_to_external, _ = active_technique_mapping(objects)
    rows = []
    for item in objects:
        description = item.get("description")
        if (
            item.get("type") != "relationship"
            or item.get("relationship_type") != "uses"
            or item.get("revoked")
            or item.get("x_mitre_deprecated")
            or not isinstance(description, str)
            or not canonical_text(description)
        ):
            continue
        target_id = active_stix_to_external.get(item.get("target_ref"))
        if target_id is None:
            continue
        rows.append(
            {
                "relationship_id": item["id"],
                "source_ref": item["source_ref"],
                "source_type": item["source_ref"].split("--", 1)[0],
                "target_id": target_id,
                "query_text": canonical_text(description),
            }
        )
    return sorted(rows, key=lambda row: row["relationship_id"])


def group_queries(rows: list[dict], seed: str = SEED) -> list[dict]:
    """Group exact-normalized procedure descriptions into multi-label records.

    A repeated official relationship description can legitimately have several
    ATT&CK targets.  It is therefore retained as one query with a set of valid
    target ids rather than turned into contradictory single-label examples.
    """
    grouped: dict[str, list[dict]] = collections.defaultdict(list)
    for row in rows:
        grouped[query_key(row["query_text"])].append(row)
    records = []
    for key, members in sorted(grouped.items()):
        source_refs = {member["source_ref"] for member in members}
        if len(source_refs) != 1:
            raise ValueError(
                "Exact-normalized procedure text spans source groups; split protocol would leak: "
                + key
            )
        canonical_member = min(members, key=lambda member: member["relationship_id"])
        source_ref = canonical_member["source_ref"]
        records.append(
            {
                "query_id": f"mitre-procedure-{key[:16]}",
                "query_sha256": key,
                "query_text": canonical_member["query_text"],
                "valid_target_ids": sorted({member["target_id"] for member in members}),
                "relationship_ids": sorted(member["relationship_id"] for member in members),
                "source_ref": source_ref,
                "source_type": canonical_member["source_type"],
                "split": split_for_source(source_ref, seed),
            }
        )
    return records


def audit_records(records: list[dict], child_to_parent: dict[str, str]) -> dict:
    per_split = {}
    for split in ("train", "dev", "test"):
        subset = [record for record in records if record["split"] == split]
        child_ids = {
            target
            for record in subset
            for target in record["valid_target_ids"]
            if target in child_to_parent
        }
        families: dict[str, set[str]] = collections.defaultdict(set)
        for child_id in child_ids:
            families[child_to_parent[child_id]].add(child_id)
        per_split[split] = {
            "query_records": len(subset),
            "relationship_rows": sum(len(record["relationship_ids"]) for record in subset),
            "source_groups": len({record["source_ref"] for record in subset}),
            "multi_target_query_records": sum(
                len(record["valid_target_ids"]) > 1 for record in subset
            ),
            "subtechnique_target_occurrences": sum(
                target in child_to_parent
                for record in subset
                for target in record["valid_target_ids"]
            ),
            "unique_subtechnique_ids": len(child_ids),
            "parent_families_with_two_or_more_child_ids": sum(
                len(ids) >= 2 for ids in families.values()
            ),
            "query_records_touching_sibling_families": sum(
                any(
                    target in child_to_parent and len(families[child_to_parent[target]]) >= 2
                    for target in record["valid_target_ids"]
                )
                for record in subset
            ),
        }
    query_splits: dict[str, set[str]] = collections.defaultdict(set)
    for record in records:
        query_splits[record["query_sha256"]].add(record["split"])
    if any(len(splits) != 1 for splits in query_splits.values()):
        raise ValueError("A normalized query appears in more than one split")
    return {
        "query_records": len(records),
        "relationship_rows": sum(len(record["relationship_ids"]) for record in records),
        "distinct_source_groups": len({record["source_ref"] for record in records}),
        "source_type_counts": dict(
            sorted(collections.Counter(record["source_type"] for record in records).items())
        ),
        "query_id_overlap_between_splits": 0,
        "per_split": per_split,
    }


def verify_mitre_lock() -> dict:
    lock = json.loads((ROOT / "data/sources.lock.json").read_text(encoding="utf-8"))
    source = next(
        item for item in lock["sources"] if item["name"] == "MITRE Enterprise ATT&CK 19.2"
    )
    for entry in source["files"]:
        path = ROOT / entry["path"]
        if not path.is_file() or sha256(path) != entry["sha256"]:
            raise ValueError(f"Missing or mismatched MITRE source: {entry['path']}")
    return source


def main() -> None:
    source = verify_mitre_lock()
    bundle = json.loads(RAW_PATH.read_text(encoding="utf-8"))
    _, child_to_parent = active_technique_mapping(bundle["objects"])
    relationship_rows = extract_relationship_rows(bundle["objects"])
    records = group_queries(relationship_rows)
    audit = audit_records(records, child_to_parent)
    if audit["relationship_rows"] != len(relationship_rows):
        raise ValueError("Relationship-row accounting mismatch")
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        "".join(
            json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records
        ),
        encoding="utf-8",
    )
    manifest = {
        "benchmark": "MITRE ATT&CK controlled procedure retrieval v1",
        "source": {
            "name": source["name"],
            "commit": source["commit"],
            "raw_sha256": sha256(RAW_PATH),
        },
        "split_protocol": {
            "unit": "relationship source_ref",
            "seed": SEED,
            "allocation": {"train": "0-69", "dev": "70-84", "test": "85-99"},
            "normalized_query_cross_split_overlap": 0,
        },
        "gold_definition": "Active Enterprise ATT&CK target technique ids of official uses relationships sharing a normalized procedure description.",
        "limitations": [
            "Controlled MITRE procedure benchmark only; not an independent raw-report benchmark.",
            "It evaluates retrieval against official ATT&CK relationship targets, not human adjudication.",
            "Corpus construction must exclude uses relationship descriptions to prevent direct procedure-text leakage.",
        ],
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Benchmark written: {OUTPUT_PATH}")
    print(
        f"Query records: {audit['query_records']}; relationship rows: {audit['relationship_rows']}"
    )


if __name__ == "__main__":
    main()
