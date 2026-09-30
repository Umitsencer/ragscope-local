"""Create a local, allowlisted submission ZIP. Never uploads or overwrites files."""

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOP_FILES = (
    "README.md",
    "SECURITY.md",
    "NOTICE.md",
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    ".gitattributes",
    ".gitignore",
    "data/sources.lock.json",
)
DIRECTORIES = (
    "src",
    "scripts",
    "tests",
    "docs",
    ".github",
    "data/audit",
    "data/derived",
    "data/evaluation",
    "data/acceptance",
)
EXTENSIONS = {".py", ".ps1", ".md", ".txt", ".json", ".jsonl", ".yml", ".yaml"}


def release_files(root: Path) -> list[Path]:
    files = [root / name for name in TOP_FILES]
    for folder in DIRECTORIES:
        base = root / folder
        if base.is_symlink():
            raise ValueError("Release directory cannot be a symlink")
        files.extend(
            path
            for path in base.rglob("*")
            if path.is_file() and path.suffix in EXTENSIONS and "__pycache__" not in path.parts
        )
    for path in files:
        if (
            not path.is_file()
            or path.is_symlink()
            or not path.resolve().is_relative_to(root.resolve())
        ):
            raise ValueError("Missing or unsafe release input")
        if path.name.lower() in ("chat.md", "chat.txt") or path.name.startswith(".env"):
            raise ValueError("Private input is not permitted in release")
    return sorted(set(files), key=lambda path: path.relative_to(root).as_posix())


def package(root: Path, destination: Path) -> dict:
    files = release_files(root)
    payloads = {path.relative_to(root).as_posix(): path.read_bytes() for path in files}
    manifest = {
        "format": "ragscope-local-submission-v1",
        "scope": "Educational evidence-inspection prototype; general QA acceptance remains unmet.",
        "files": {
            name: {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            for name, data in payloads.items()
        },
        "excluded": [
            "raw datasets",
            "model weights",
            "embedding caches",
            "virtual environment",
            "private conversations",
            "credentials",
        ],
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in payloads.items():
            archive.writestr("ragscope-local/" + name, data)
        archive.writestr("ragscope-local/SUBMISSION_MANIFEST.json", json.dumps(manifest, indent=2))
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP integrity failed")
        for name, metadata in manifest["files"].items():
            if (
                hashlib.sha256(archive.read("ragscope-local/" + name)).hexdigest()
                != metadata["sha256"]
            ):
                raise ValueError("ZIP payload hash mismatch")
    return {
        "file_count": len(files),
        "zip_bytes": destination.stat().st_size,
        "zip_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    target = args.output.resolve()
    if not target.is_relative_to((ROOT / "dist").resolve()) or target.suffix != ".zip":
        parser.error("Output must be a new .zip inside dist/")
    print(json.dumps(package(ROOT, target), indent=2))


if __name__ == "__main__":
    main()
