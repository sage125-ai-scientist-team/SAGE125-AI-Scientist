"""Offline fail-closed validator for T09 Wave C packaging manifests."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath


def sha256(path: Path) -> str:
    """Return the raw-byte SHA-256 identity for one inventory file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_path(value: object) -> PurePosixPath | None:
    """Accept only a non-empty relative POSIX path inside the package root."""
    if not isinstance(value, str) or not value:
        return None
    path = PurePosixPath(value.replace("\\", "/"))
    if path.is_absolute() or any(part in {".", ".."} for part in path.parts):
        return None
    return path


def validate(manifest_path: Path, package_root: Path) -> dict[str, object]:
    """Validate count, provenance, path safety and raw-byte checksums offline."""
    errors: list[str] = []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return {"passed": False, "errors": [f"manifest:{type(error).__name__}"]}
    if not isinstance(manifest, dict):
        return {"passed": False, "errors": ["manifest:shape"]}
    entries = manifest.get("files")
    expected = manifest.get("expected_file_count")
    if not isinstance(expected, int) or expected < 1:
        errors.append("expected_file_count")
    if not isinstance(entries, list):
        return {"passed": False, "errors": errors + ["files"]}
    if expected != len(entries):
        errors.append("file_count")
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            errors.append("entry:shape")
            continue
        if not isinstance(entry.get("provenance"), str) or not entry["provenance"]:
            errors.append("entry:provenance")
        relative = safe_path(entry.get("path"))
        if relative is None:
            errors.append("entry:path")
            continue
        name = relative.as_posix()
        if name in seen:
            errors.append("entry:duplicate")
        seen.add(name)
        expected_hash = entry.get("sha256")
        if not isinstance(expected_hash, str) or len(expected_hash) != 64:
            errors.append("entry:sha256")
            continue
        actual = package_root.joinpath(*relative.parts)
        if not actual.is_file():
            errors.append("entry:missing")
        elif sha256(actual) != expected_hash:
            errors.append("entry:sha256_drift")
    return {"passed": not errors, "errors": sorted(set(errors)), "provider_calls": 0}


def main() -> int:
    """Print a JSON result and exit non-zero for every invalid package."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--package-root", type=Path, required=True)
    args = parser.parse_args()
    report = validate(args.manifest, args.package_root)
    print(json.dumps(report, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
