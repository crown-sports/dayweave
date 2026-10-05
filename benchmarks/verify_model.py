"""Verify a pinned public model manifest against local inference files without copying weights."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path


def verify(directory: Path, manifest: dict) -> dict:
    """Stream every file and compare either its content SHA-256 or its Git-blob SHA-1."""
    verified = []
    for item in manifest["files"]:
        name = item["file"]
        if Path(name).name != name:
            raise ValueError("Inference manifest entries must be filenames")
        path = directory / name
        size = path.stat().st_size
        algorithm = "sha256" if "sha256" in item else "git_blob_sha1"
        digest = hashlib.sha256() if algorithm == "sha256" else hashlib.sha1()
        if algorithm == "git_blob_sha1":
            digest.update(f"blob {size}\0".encode())
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                digest.update(block)
        if size != item["size"] or digest.hexdigest() != item[algorithm]:
            raise RuntimeError("Inference file did not match the pinned manifest: " + name)
        verified.append({**item, "verified": True})
    return {
        **manifest,
        "files": verified,
        "verified_at": datetime.now(UTC).isoformat(),
        "verification": "All listed inference files rehashed and matched the pinned public manifest.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = verify(args.directory, json.loads(args.manifest.read_text()))
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Verified {len(result['files'])} inference files for {result['model']} at {result['revision']}")


if __name__ == "__main__":
    main()
