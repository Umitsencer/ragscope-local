"""Reproducible, read-only audit of pinned CTIConnect ATA and ATT&CK 19.2.

Usage: python -B scripts/audit_sources.py
Writes only data/audit/ata_audit.json; does not download or alter raw files.
"""

from __future__ import annotations

import collections
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "data" / "sources.lock.json"
OUTPUT = ROOT / "data" / "audit" / "ata_audit.json"
ID_RE = re.compile(r"^T\d{4}(?:\.\d{3})?$")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_sources(lock: dict) -> None:
    for source in lock["sources"]:
        for entry in source["files"]:
            path = ROOT / entry["path"]
            if not path.is_file():
                raise FileNotFoundError(f"Pinned source missing: {path}")
            actual = sha256(path)
            if actual != entry["sha256"]:
                raise ValueError(f"SHA-256 mismatch: {entry['path']}: {actual}")


def attack_mapping(objects: list[dict]) -> tuple[dict[str, dict], dict[str, str], dict]:
    all_patterns = [item for item in objects if item.get("type") == "attack-pattern"]
    by_id = {item["id"]: item for item in all_patterns}
    external = {}
    for item in all_patterns:
        for reference in item.get("external_references", []):
            if reference.get("source_name") == "mitre-attack" and ID_RE.fullmatch(
                reference.get("external_id", "")
            ):
                external[reference["external_id"]] = item
    active = {
        key: item
        for key, item in external.items()
        if not item.get("revoked") and not item.get("x_mitre_deprecated")
    }
    stix_to_external = {item["id"]: key for key, item in active.items()}
    child_to_parent = {}
    for item in objects:
        if (
            item.get("type") == "relationship"
            and item.get("relationship_type") == "subtechnique-of"
            and not item.get("revoked")
            and not item.get("x_mitre_deprecated")
        ):
            child = by_id.get(item.get("source_ref"))
            parent = by_id.get(item.get("target_ref"))
            if child and parent:
                child_id = stix_to_external.get(child["id"])
                parent_id = stix_to_external.get(parent["id"])
                if child_id and parent_id:
                    child_to_parent[child_id] = parent_id
    counts = {
        "stix_objects": len(objects),
        "active_techniques": sum(
            not item.get("x_mitre_is_subtechnique", False) for item in active.values()
        ),
        "active_subtechniques": sum(
            bool(item.get("x_mitre_is_subtechnique", False)) for item in active.values()
        ),
        "active_child_parent_links": len(child_to_parent),
    }
    return external, child_to_parent, counts


def audit_ata(rows: list[dict], external: dict[str, dict], child_to_parent: dict[str, str]) -> dict:
    ids = [row["id"] for row in rows]
    source_ids = [row["source"]["source_id"] for row in rows]
    labels = [label for row in rows for label in row["ground_truth"]["target_ids"]]
    label_counts = collections.Counter(labels)
    source_counts = collections.Counter(source_ids)
    question_groups = collections.defaultdict(list)
    for row in rows:
        question_groups[row["question"].strip()].append(row["id"])
    duplicate_question_ids = [sorted(group) for group in question_groups.values() if len(group) > 1]
    label_state = collections.Counter()
    unmatched = {}
    family_labels: dict[str, set[str]] = collections.defaultdict(set)
    family_rows = collections.Counter()
    family_sources: dict[str, set[str]] = collections.defaultdict(set)
    for row in rows:
        for label in row["ground_truth"]["target_ids"]:
            object_ = external.get(label)
            if (
                object_ is not None
                and not object_.get("revoked")
                and not object_.get("x_mitre_deprecated")
            ):
                parent = child_to_parent.get(label, label)
                family_sources[parent].add(row["source"]["source_id"])
    for label in labels:
        object_ = external.get(label)
        if object_ is None:
            label_state["missing_from_enterprise_19_2"] += 1
            unmatched[label] = "missing_from_enterprise_19_2"
            continue
        if object_.get("revoked"):
            label_state["revoked_in_19_2"] += 1
            unmatched[label] = "revoked_in_19_2"
            continue
        if object_.get("x_mitre_deprecated"):
            label_state["deprecated_in_19_2"] += 1
            unmatched[label] = "deprecated_in_19_2"
            continue
        label_state["active_in_19_2"] += 1
        parent = child_to_parent.get(label, label)
        family_labels[parent].add(label)
        family_rows[parent] += 1
    sibling_families = sorted(
        parent
        for parent, members in family_labels.items()
        if sum(member != parent for member in members) >= 2
    )
    parent_and_child_families = sorted(
        parent
        for parent, members in family_labels.items()
        if parent in members and any(member != parent for member in members)
    )
    question_target_id_leakage = sum(
        any(
            re.search(
                r"(?<![A-Za-z0-9])" + re.escape(label) + r"(?![A-Za-z0-9])", row["question"], re.I
            )
            for label in row["ground_truth"]["target_ids"]
        )
        for row in rows
    )
    conflicting_duplicate_questions = []
    rows_by_id = {row["id"]: row for row in rows}
    for group in duplicate_question_ids:
        target_sets = {
            tuple(sorted(rows_by_id[record_id]["ground_truth"]["target_ids"]))
            for record_id in group
        }
        if len(target_sets) > 1:
            conflicting_duplicate_questions.append(
                {
                    "record_ids": group,
                    "target_sets": [list(target_set) for target_set in sorted(target_sets)],
                    "source_ids": sorted(
                        {rows_by_id[record_id]["source"]["source_id"] for record_id in group}
                    ),
                }
            )
    return {
        "records": len(rows),
        "unique_record_ids": len(set(ids)),
        "unique_source_ids": len(source_counts),
        "source_group_size_histogram": dict(
            sorted(collections.Counter(source_counts.values()).items())
        ),
        "labels_total": len(labels),
        "labels_unique": len(label_counts),
        "items_with_multiple_labels": sum(
            len(row["ground_truth"]["target_ids"]) > 1 for row in rows
        ),
        "subtechnique_form_labels": sum("." in label for label in labels),
        "label_state_against_19_2": dict(sorted(label_state.items())),
        "unmatched_labels": dict(sorted(unmatched.items())),
        "sibling_families_with_two_or_more_distinct_child_labels": sibling_families,
        "sibling_family_count": len(sibling_families),
        "parent_and_child_labeled_families": parent_and_child_families,
        "parent_and_child_family_count": len(parent_and_child_families),
        "rows_in_sibling_families": sum(family_rows[parent] for parent in sibling_families),
        "sibling_family_support": {
            parent: {
                "rows": family_rows[parent],
                "source_groups": len(family_sources[parent]),
                "child_labels": sorted(label for label in family_labels[parent] if label != parent),
                "parent_labeled": parent in family_labels[parent],
            }
            for parent in sibling_families
        },
        "question_contains_gold_id_count": question_target_id_leakage,
        "exact_duplicate_question_record_groups": sorted(duplicate_question_ids),
        "conflicting_duplicate_questions": conflicting_duplicate_questions,
        "duplicate_record_ids": sorted(
            key for key, count in collections.Counter(ids).items() if count > 1
        ),
        "published_split_field_present": any("split" in row for row in rows),
    }


def main() -> None:
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    verify_sources(lock)
    manifest = json.loads((ROOT / "data/raw/cticonnect/manifest.json").read_text(encoding="utf-8"))
    rows = [
        json.loads(line)
        for line in (ROOT / "data/raw/cticonnect/ata.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    bundle = json.loads(
        (ROOT / "data/raw/mitre/enterprise-attack-19.2.json").read_text(encoding="utf-8")
    )
    external, child_to_parent, attack_counts = attack_mapping(bundle["objects"])
    result = {
        "source_lock_sha256": sha256(LOCK),
        "manifest_total": manifest["total_count"],
        "manifest_task_count_sum": sum(task["count"] for task in manifest["tasks"].values()),
        "manifest_ata_count": manifest["tasks"]["ata"]["count"],
        "manifest_ata_sha256_matches": manifest["tasks"]["ata"]["sha256"]
        == sha256(ROOT / "data/raw/cticonnect/ata.jsonl"),
        "attack": attack_counts,
        "ata": audit_ata(rows, external, child_to_parent),
    }
    if result["ata"]["records"] != result["manifest_ata_count"]:
        raise ValueError("ATA record count differs from the pinned manifest")
    if not result["manifest_ata_sha256_matches"]:
        raise ValueError("ATA SHA-256 differs from the pinned manifest")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Audit written: {OUTPUT}")
    print(
        f"ATA rows: {result['ata']['records']}; sibling families: {result['ata']['sibling_family_count']}"
    )


if __name__ == "__main__":
    main()
