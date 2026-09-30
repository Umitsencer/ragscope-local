"""Offline syntax, UTF-8, local Markdown link and artifact-hash checks."""

import ast
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"\]\(([^)]+)\)")


def main():
    checked_links = 0
    files = [ROOT / "README.md", ROOT / "NOTICE.md", *sorted((ROOT / "docs").glob("*.md"))]
    for path in files:
        content = path.read_text(encoding="utf-8")
        if "\ufffd" in content:
            raise ValueError(f"Encoding replacement character: {path.name}")
        for target in LINK.findall(content):
            if target.startswith(("https:", "http:", "mailto:", "#")):
                continue
            target = unquote(target.split("#")[0].strip("<>"))
            if not (path.parent / target).is_file():
                raise ValueError(f"Broken link in {path.name}: {target}")
            checked_links += 1
    python_files = [
        *sorted((ROOT / "src").rglob("*.py")),
        *sorted((ROOT / "scripts").glob("*.py")),
        *sorted((ROOT / "tests").glob("*.py")),
    ]
    for path in python_files:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    expected = {
        "corpus_sha256": hashlib.sha256(
            (ROOT / "data/derived/mitre_definition_corpus.jsonl").read_bytes()
        ).hexdigest(),
        "benchmark_sha256": hashlib.sha256(
            (ROOT / "data/derived/mitre_procedure_benchmark.jsonl").read_bytes()
        ).hexdigest(),
    }
    artifacts = list((ROOT / "data/evaluation").glob("*.json"))
    for path in artifacts:
        value = json.loads(path.read_text(encoding="utf-8"))
        for key, digest in expected.items():
            if key in value and value[key] != digest:
                raise ValueError(f"Artifact input hash mismatch: {path.name}: {key}")
    print(
        f"PASS: {len(python_files)} Python files; {checked_links} local links; {len(artifacts)} evaluation JSON files"
    )


if __name__ == "__main__":
    main()
