"""Count AnnoCTR MITRE-only linking labels without emitting vendor text.

Usage: python -B scripts/audit_annoctr.py
Writes only data/audit/annoctr_audit.json.
"""

from __future__ import annotations

import collections
import json
import re

from audit_sources import ROOT, attack_mapping, sha256

OUTPUT = ROOT / "data/audit/annoctr_audit.json"
TECHNIQUE_URL = re.compile(r"https://attack\.mitre\.org/techniques/(T\d{4})(?:/(\d{3}))?/?")


def technique_id(link: str) -> str | None:
    match = TECHNIQUE_URL.fullmatch(link)
    if not match:
        return None
    return match.group(1) + ("." + match.group(2) if match.group(2) else "")


def audit_split(
    rows: list[dict], active_enterprise: set[str], child_to_parent: dict[str, str]
) -> dict:
    techniques = [row for row in rows if row.get("entity_type") == "TECHNIQUE"]
    ids = [technique_id(row.get("label_link", "")) for row in techniques]
    valid_ids = [value for value in ids if value is not None]
    sub_ids = [value for value in valid_ids if "." in value]
    sub_counts = collections.Counter(sub_ids)
    active_sub = [value for value in sub_ids if value in child_to_parent]
    families = collections.defaultdict(set)
    for value in active_sub:
        families[child_to_parent[value]].add(value)
    return {
        "all_linking_rows": len(rows),
        "technique_type_rows": len(techniques),
        "technique_type_non_technique_urls": len(techniques) - len(valid_ids),
        "technique_url_rows": len(valid_ids),
        "unique_technique_ids": len(set(valid_ids)),
        "subtechnique_url_rows": len(sub_ids),
        "subtechnique_id_counts": dict(sorted(sub_counts.items())),
        "active_enterprise_19_2_technique_url_rows": sum(
            value in active_enterprise for value in valid_ids
        ),
        "active_enterprise_19_2_subtechnique_rows": len(active_sub),
        "enterprise_parent_families_with_two_or_more_child_ids": sum(
            len(members) >= 2 for members in families.values()
        ),
        "unique_documents_all_rows": len({row["document"] for row in rows}),
        "unique_documents_technique_rows": len({row["document"] for row in techniques}),
        "entity_type_counts": dict(
            sorted(collections.Counter(row["entity_type"] for row in rows).items())
        ),
    }


def main() -> None:
    lock = json.loads((ROOT / "data/sources.lock.json").read_text(encoding="utf-8"))
    source = next(item for item in lock["sources"] if item["name"] == "AnnoCTR MITRE-only linking")
    for entry in source["files"]:
        path = ROOT / entry["path"]
        if not path.is_file() or sha256(path) != entry["sha256"]:
            raise ValueError(f"Missing or mismatched source: {entry['path']}")
    bundle = json.loads(
        (ROOT / "data/raw/mitre/enterprise-attack-19.2.json").read_text(encoding="utf-8")
    )
    external, child_to_parent, _ = attack_mapping(bundle["objects"])
    active = {
        key
        for key, value in external.items()
        if not value.get("revoked") and not value.get("x_mitre_deprecated")
    }
    splits = {}
    documents = {}
    for name in ("train", "dev", "test"):
        rows = [
            json.loads(line)
            for line in (ROOT / f"data/raw/annoctr/{name}.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        ]
        splits[name] = audit_split(rows, active, child_to_parent)
        documents[name] = {row["document"] for row in rows}
    overlaps = {
        f"{left}_{right}": len(documents[left] & documents[right])
        for left, right in (("train", "dev"), ("train", "test"), ("dev", "test"))
    }
    result = {
        "source_commit": source["commit"],
        "splits": splits,
        "document_overlap_between_splits": overlaps,
        "raw_text_in_output": False,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Audit written: {OUTPUT}")
    for name, value in splits.items():
        print(
            f"{name}: {value['technique_url_rows']} technique rows; {value['active_enterprise_19_2_subtechnique_rows']} active Enterprise sub-technique rows"
        )


if __name__ == "__main__":
    main()
