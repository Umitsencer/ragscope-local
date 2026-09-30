"""Fetch only commit-pinned source files, verifying bytes before publication.

Existing files are checked, never replaced. Default mode only checks local files;
network access requires --download. Temporary downloads are removed on failure.
"""

import argparse
import hashlib
import json
import re
import tempfile
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def resolve_entry(root, source, entry):
    raw_root = (root / "data/raw").resolve()
    target = (root / entry["path"]).resolve()
    if not target.is_relative_to(raw_root) or target == raw_root:
        raise ValueError("Source destination must be inside data/raw")
    repo = urlparse(source["repository"])
    if (
        repo.scheme != "https"
        or repo.netloc != "github.com"
        or not re.fullmatch(r"/[\w.-]+/[\w.-]+", repo.path)
    ):
        raise ValueError("Expected a GitHub HTTPS repository")
    if not re.fullmatch(r"[0-9a-f]{40}", source["commit"]):
        raise ValueError("Expected an exact commit")
    relative = PurePosixPath(entry["source_path"])
    if relative.is_absolute() or ".." in relative.parts or "\\" in entry["source_path"]:
        raise ValueError("Invalid source path")
    if not re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]):
        raise ValueError("Expected SHA-256")
    url = f"https://raw.githubusercontent.com{repo.path}/{source['commit']}/{relative}"
    return target, url


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def fetch_entry(root, source, entry, download=False, opener=urlopen):
    target, url = resolve_entry(root, source, entry)
    if target.exists():
        if digest(target) != entry["sha256"]:
            raise ValueError(f"Existing file hash mismatch: {entry['path']}; retained unchanged")
        return "verified"
    if not download:
        raise FileNotFoundError(f"Missing: {entry['path']}; use --download to fetch")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
            temporary = Path(stream.name)
            with opener(url, timeout=60) as response:
                total = 0
                while block := response.read(1024 * 1024):
                    total += len(block)
                    if total > 100 * 1024 * 1024:
                        raise ValueError("Source exceeds 100 MiB limit")
                    stream.write(block)
        if digest(temporary) != entry["sha256"]:
            raise ValueError(f"Download hash mismatch: {entry['path']}")
        # Hard-link creation is atomic and refuses to overwrite a concurrent file.
        target.hardlink_to(temporary)
        return "downloaded and verified"
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    lock = json.loads((ROOT / "data/sources.lock.json").read_text(encoding="utf-8"))
    for source in lock["sources"]:
        for entry in source["files"]:
            print(f"{entry['path']}: {fetch_entry(ROOT, source, entry, args.download)}")


if __name__ == "__main__":
    main()
