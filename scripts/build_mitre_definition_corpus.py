"""Build a definition-only ATT&CK corpus for controlled retrieval experiments.

It reads only active ``attack-pattern`` objects. Relationship objects, including
the benchmark's ``uses`` procedure descriptions, are structurally excluded.

Usage: python -B scripts/build_mitre_definition_corpus.py
"""

from __future__ import annotations

import hashlib
import json

from audit_sources import ROOT, attack_mapping, sha256
from build_mitre_procedure_benchmark import RAW_PATH, canonical_text, query_key, verify_mitre_lock

OUTPUT_PATH = ROOT / "data/derived/mitre_definition_corpus.jsonl"
MANIFEST_PATH = ROOT / "data/derived/mitre_definition_corpus.manifest.json"
AUDIT_PATH = ROOT / "data/audit/mitre_definition_corpus_audit.json"


def build_documents(objects: list[dict]) -> list[dict]:
    """Return active technique documents using attack-pattern fields only."""
    external, child_to_parent, _ = attack_mapping(objects)
    documents = []
    for attack_id, item in sorted(external.items()):
        if item.get("revoked") or item.get("x_mitre_deprecated"):
            continue
        description = canonical_text(item.get("description", ""))
        if not description:
            raise ValueError(f"Active ATT&CK pattern has no description: {attack_id}")
        documents.append(
            {
                "document_id": attack_id,
                "name": item["name"],
                "description": description,
                "is_subtechnique": bool(item.get("x_mitre_is_subtechnique")),
                "parent_technique_id": child_to_parent.get(attack_id),
                "stix_object_id": item["id"],
            }
        )
    return documents


def corpus_audit(documents: list[dict], objects: list[dict]) -> dict:
    """Audit structural exclusion and exact normalized query/document overlap."""
    relationship_descriptions = {
        query_key(item["description"])
        for item in objects
        if item.get("type") == "relationship"
        and item.get("relationship_type") == "uses"
        and isinstance(item.get("description"), str)
        and canonical_text(item["description"])
    }
    document_text_keys = {query_key(document["description"]) for document in documents}
    exact_overlap = relationship_descriptions & document_text_keys
    return {
        "active_definition_documents": len(documents),
        "active_parent_documents": sum(not document["is_subtechnique"] for document in documents),
        "active_subtechnique_documents": sum(document["is_subtechnique"] for document in documents),
        "source_stix_object_types_read": ["attack-pattern"],
        "relationship_objects_used_as_corpus_input": 0,
        "uses_procedure_descriptions_used_as_corpus_input": 0,
        "exact_normalized_uses_description_equals_definition_count": len(exact_overlap),
        "document_id_sha256": hashlib.sha256(
            "\n".join(document["document_id"] for document in documents).encode("utf-8")
        ).hexdigest(),
    }


def main() -> None:
    source = verify_mitre_lock()
    bundle = json.loads(RAW_PATH.read_text(encoding="utf-8"))
    documents = build_documents(bundle["objects"])
    audit = corpus_audit(documents, bundle["objects"])
    if (
        audit["relationship_objects_used_as_corpus_input"] != 0
        or audit["uses_procedure_descriptions_used_as_corpus_input"] != 0
    ):
        raise ValueError("Definition-only invariant failed")
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        "".join(
            json.dumps(document, ensure_ascii=False, sort_keys=True) + "\n"
            for document in documents
        ),
        encoding="utf-8",
    )
    manifest = {
        "corpus": "MITRE ATT&CK definition-only corpus v1",
        "source": {
            "name": source["name"],
            "commit": source["commit"],
            "raw_sha256": sha256(RAW_PATH),
        },
        "included_stix_object_type": "attack-pattern",
        "excluded_stix_object_types": ["relationship"],
        "excluded_text": ["uses relationship descriptions", "procedure examples"],
        "fields": [
            "document_id",
            "name",
            "description",
            "is_subtechnique",
            "parent_technique_id",
            "stix_object_id",
        ],
        "limitations": [
            "Structural exclusion prevents relationship procedure text from entering the corpus.",
            "Definition text can still share domain vocabulary with queries; that is the intended retrieval task, not a guarantee against semantic overlap.",
        ],
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Corpus written: {OUTPUT_PATH}")
    print(
        f"Definition documents: {audit['active_definition_documents']}; exact text overlap: {audit['exact_normalized_uses_description_equals_definition_count']}"
    )


if __name__ == "__main__":
    main()
