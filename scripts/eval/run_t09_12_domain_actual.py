"""Run the governed T09 twelve-domain evaluation with resumable, auditable ledgers."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.call_audit import summarize_calls  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.workflow.artifacts import resolve_artifact_base  # noqa: E402
from app.workflow.pipeline import run_pipeline_with_state  # noqa: E402


PROTOCOL_PATH = PROJECT_ROOT / "docs" / "reproducibility" / "T09_12_DOMAIN_SCORING_PROTOCOL.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "exports" / "t09_12_domain_actual"
MAX_ATTEMPT_CAP = 24
MAX_RETRIES_PER_ENTRY = 1
_RETRYABLE_ERRORS = (TimeoutError, ConnectionError, OSError)
_SECRET_PATTERNS = (
    re.compile(r"(?i)(?:api[_-]?key|authorization|bearer|password|secret)\s*[:=]\s*['\"]?[A-Za-z0-9_\-/]{8,}"),
    re.compile(r"(?i)sk-[A-Za-z0-9]{12,}"),
)


def sha256_file(path: Path) -> str:
    """Return the lowercase SHA-256 digest of a file without loading it all at once."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_sha256(path: Path) -> str:
    """Hash a JSON object after deterministic serialization, ignoring source formatting."""
    value = load_json(path)
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON object or raise a clear ValueError for invalid input."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid_json:{path}:{type(error).__name__}") from error
    if not isinstance(value, dict):
        raise ValueError(f"invalid_object:{path}")
    return value


def _utc_now() -> str:
    """Return an ISO-8601 UTC timestamp for a ledger event."""
    return datetime.now(timezone.utc).isoformat()


def _safe_environment() -> dict[str, str | bool]:
    """Record only non-secret execution toggles; API keys are never copied to outputs."""
    return {
        "MOCK_LLM": os.getenv("MOCK_LLM", "").strip().lower() in {"1", "true", "yes"},
        "SAGE_TEST_EXPORT_DIR": bool(os.getenv("SAGE_TEST_EXPORT_DIR")),
        "EXPORT_DIR": bool(os.getenv("EXPORT_DIR")),
    }


def _source_identity(source: dict[str, Any]) -> tuple[Path, str | None, str | None]:
    """Resolve a source path and return its observed canonical path and SHA-256."""
    source_path = Path(str(source.get("path", "")))
    source_path = source_path if source_path.is_absolute() else PROJECT_ROOT / source_path
    source_path = source_path.resolve()
    if not source_path.is_file():
        return source_path, None, None
    return source_path, str(source_path), sha256_file(source_path)


def preflight(manifest_path: Path, protocol_path: Path = PROTOCOL_PATH) -> dict[str, Any]:
    """Validate canonical hashes, source identity, provider-safe schema, and domain coverage."""
    protocol = load_json(protocol_path)
    manifest = load_json(manifest_path)
    errors: list[str] = []
    required_domains = protocol.get("required_domains")
    entries = manifest.get("domains")
    if protocol.get("schema_version") != "1.1" or not isinstance(required_domains, list):
        errors.append("protocol_shape")
    if manifest.get("schema_version") != "1.0" or not isinstance(entries, list):
        errors.append("manifest_shape")
        entries = []
    try:
        manifest_sha = canonical_json_sha256(manifest_path)
    except ValueError:
        manifest_sha = ""
    source = manifest.get("question_source")
    if not isinstance(source, dict):
        errors.append("question_source")
    else:
        source_path, canonical_path, observed_sha = _source_identity(source)
        expected_sha = source.get("sha256")
        identity = source.get("identity")
        if not isinstance(expected_sha, str) or len(expected_sha) != 64 or observed_sha != expected_sha:
            errors.append("question_source_sha256")
        if not isinstance(identity, dict):
            errors.append("question_source_identity")
        elif (
            identity.get("canonical_path") != canonical_path
            or identity.get("sha256") != observed_sha
            or identity.get("sha256") != expected_sha
        ):
            errors.append("question_source_identity")
    domains = [item.get("domain") for item in entries if isinstance(item, dict)]
    question_ids = [item.get("question_id") for item in entries if isinstance(item, dict)]
    if domains != required_domains or len(domains) != 12 or len(set(domains)) != 12:
        errors.append("domain_coverage")
    if any(not isinstance(question_id, str) or not question_id for question_id in question_ids):
        errors.append("question_id")
    if len(set(question_ids)) != len(question_ids):
        errors.append("duplicate_question_id")
    return {
        "passed": not errors,
        "errors": sorted(set(errors)),
        "manifest_sha256": manifest_sha,
        "manifest_hash_algorithm": "sha256-canonical-json-v1",
        "required_domain_count": len(required_domains) if isinstance(required_domains, list) else 0,
        "environment": _safe_environment(),
        "provider_calls": 0,
    }


def _write_json(path: Path, value: dict[str, Any]) -> None:
    """Atomically write one formatted JSON artifact so interrupted writes cannot corrupt it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp"
    ) as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
        temp_path = Path(handle.name)
    os.replace(temp_path, path)


def _retryable(error: Exception) -> bool:
    """Classify only transient transport failures as safe for the single retry."""
    return isinstance(error, _RETRYABLE_ERRORS)


def _artifact_integrity(path: Path) -> dict[str, Any]:
    """Return deterministic artifact hashes and a redacted secret-scan result."""
    files = [path] if path.is_file() else sorted(item for item in path.rglob("*") if item.is_file())
    digest = hashlib.sha256()
    secret_matches = 0
    for file_path in files:
        relative = file_path.name if path.is_file() else file_path.relative_to(path).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_path.read_bytes())
        try:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            text = ""
        secret_matches += sum(len(pattern.findall(text)) for pattern in _SECRET_PATTERNS)
    return {
        "path": str(path),
        "file_count": len(files),
        "sha256": digest.hexdigest(),
        "secret_scan": {"passed": secret_matches == 0, "match_count": secret_matches},
    }


def _load_resume_ledger(path: Path, manifest_sha256: str) -> dict[str, Any] | None:
    """Load a compatible ledger only when resume was explicitly requested."""
    if not path.is_file():
        return None
    ledger = load_json(path)
    if ledger.get("manifest_sha256") != manifest_sha256:
        raise ValueError("resume_manifest_identity_mismatch")
    return ledger


def _completed_questions(ledger: dict[str, Any]) -> set[str]:
    """Return question IDs with a completed and integrity-checked terminal attempt."""
    completed: set[str] = set()
    for entry in ledger.get("entries", []):
        if not isinstance(entry, dict):
            continue
        attempts = entry.get("attempts", [])
        if attempts and isinstance(attempts[-1], dict) and attempts[-1].get("status") == "completed":
            completed.add(str(entry.get("question_id", "")))
    return completed


def run(
    manifest_path: Path,
    output_dir: Path = DEFAULT_OUTPUT,
    *,
    execute: bool = False,
    mock: bool = False,
    attempt_cap: int = 1,
    retry: bool = False,
    resume: bool = False,
) -> dict[str, Any]:
    """Run preflight by default; execute only when config gates and explicit flags allow it."""
    if not 1 <= attempt_cap <= MAX_ATTEMPT_CAP:
        raise ValueError(f"attempt_cap must be between 1 and {MAX_ATTEMPT_CAP}")
    report = preflight(manifest_path)
    ledger_path = output_dir / "ledger.json"
    ledger = {
        "schema_version": "1.0",
        "created_at": _utc_now(),
        "mode": "execute" if execute else "preflight-only",
        "mock": mock,
        "attempt_cap": attempt_cap,
        "manifest": str(manifest_path),
        "manifest_sha256": report["manifest_sha256"],
        "manifest_hash_algorithm": report["manifest_hash_algorithm"],
        "environment": report["environment"],
        "entries": [],
        "provider_calls": 0,
        "token_count": None,
        "cost_usd": None,
        "stopped": False,
    }
    if execute and not mock and not get_settings().qwen_configured:
        report["errors"] = sorted(set([*report["errors"], "provider_not_configured"]))
        report["passed"] = False
    if not report["passed"] or not execute:
        report.update({"mode": "preflight-only", "ledger_path": str(ledger_path), "executed": False})
        ledger["preflight"] = report
        _write_json(ledger_path, ledger)
        _write_json(output_dir / "preflight.json", report)
        return report

    manifest = load_json(manifest_path)
    total_provider_calls = 0
    artifact_base = resolve_artifact_base(
        "exports" if mock else get_settings().export_dir
    )
    if resume:
        previous = _load_resume_ledger(ledger_path, report["manifest_sha256"])
        if previous is not None:
            ledger = previous
            ledger["resumed_at"] = _utc_now()
    completed_questions = _completed_questions(ledger)
    for item in manifest["domains"]:
        if item["question_id"] in completed_questions:
            continue
        entry: dict[str, Any] = {"domain": item["domain"], "question_id": item["question_id"], "attempts": []}
        max_attempts = 1 + (MAX_RETRIES_PER_ENTRY if retry else 0)
        for attempt in range(1, min(attempt_cap, max_attempts) + 1):
            try:
                _, state = run_pipeline_with_state(
                    item["question_id"],
                    mock_mode=mock,
                    use_local_rag=not mock,
                    use_deep_research=not mock,
                    use_open_literature=not mock,
                )
                summary = summarize_calls(state.llm_calls)
                total_provider_calls += int(summary["real_qwen_calls"])
                artifact_path = artifact_base / state.run_id
                integrity = _artifact_integrity(artifact_path) if artifact_path.exists() else None
                if integrity is None or not integrity["secret_scan"]["passed"]:
                    raise ValueError("artifact_integrity_failure")
                entry["attempts"].append(
                    {
                        "attempt": attempt,
                        "status": "completed",
                        "run_id": state.run_id,
                        "artifact": integrity,
                        "call_summary": summary,
                        "token_count": None,
                        "cost_usd": None,
                    }
                )
                break
            except Exception as error:
                retryable = _retryable(error)
                entry["attempts"].append(
                    {
                        "attempt": attempt,
                        "status": "failed",
                        "error_type": type(error).__name__,
                        "retryable": retryable,
                        "token_count": None,
                        "cost_usd": None,
                    }
                )
                if retryable and retry and attempt < min(attempt_cap, max_attempts):
                    continue
                ledger["entries"].append(entry)
                ledger["stopped"] = True
                ledger["stop_reason"] = "retry_exhausted" if retryable else "non_retryable_failure"
                ledger["provider_calls"] = total_provider_calls
                ledger["completed_at"] = _utc_now()
                _write_json(ledger_path, ledger)
                report.update(
                    {
                        "passed": False,
                        "mode": "execute",
                        "executed": True,
                        "provider_calls": total_provider_calls,
                        "ledger_path": str(ledger_path),
                    }
                )
                _write_json(output_dir / "run_summary.json", report)
                return report
        ledger["entries"].append(entry)
    ledger["provider_calls"] = total_provider_calls
    ledger["metric_coverage"] = {
        "requirement_id": "T09-METRIC-005",
        "evaluated_domain_count": len(_completed_questions(ledger)),
        "required_domain_count": 12,
        "passed": len(_completed_questions(ledger)) == 12,
    }
    ledger["completed_at"] = _utc_now()
    _write_json(ledger_path, ledger)
    report.update(
        {
            "mode": "execute",
            "executed": True,
            "provider_calls": total_provider_calls,
            "ledger_path": str(ledger_path),
        }
    )
    _write_json(output_dir / "run_summary.json", report)
    return report


def main() -> int:
    """Parse CLI arguments, write governed artifacts, and fail on invalid preflight."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--execute", action="store_true", help="Allow real Provider execution.")
    parser.add_argument("--mock", action="store_true", help="Execute the pipeline in mock mode.")
    parser.add_argument("--attempt-cap", type=int, default=1)
    parser.add_argument("--retry", action="store_true", help="Retry failed entries within the attempt cap.")
    parser.add_argument("--resume", action="store_true", help="Resume only a ledger with the same canonical manifest hash.")
    args = parser.parse_args()
    report = run(
        args.manifest, args.output_dir, execute=args.execute, mock=args.mock,
        attempt_cap=args.attempt_cap, retry=args.retry, resume=args.resume,
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return int(not report["passed"])


if __name__ == "__main__":
    raise SystemExit(main())
