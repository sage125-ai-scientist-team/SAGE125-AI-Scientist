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
from app.workflow.pipeline import resolve_questions_path, run_pipeline_with_state  # noqa: E402


PROTOCOL_PATH = PROJECT_ROOT / "docs" / "reproducibility" / "T09_12_DOMAIN_SCORING_PROTOCOL.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "exports" / "t09_12_domain_actual"
MAX_ATTEMPT_CAP = 24
MAX_RETRIES_PER_ENTRY = 1
EXPECTED_PROVIDER = "bailian"
EXPECTED_MODEL = "qwen3.6-flash"
EXPECTED_REGION = "cn-beijing"
EXPECTED_ENDPOINT_SUFFIX = ".maas.aliyuncs.com/compatible-mode/v1"
FORMAL_QUESTION_SOURCE_PATH = "data/processed/questions_125.json"
FORMAL_QUESTION_SOURCE_SHA256 = "b6712a3b53f9776d7f695ea67f810c30b7d97ee59c183009432870d3224cdebb"
APPROVAL_SOURCE = "T09_BATCH_4B_SCHEMA_CONFORMANCE_AUTHORIZATION"
APPROVED_DOMAIN_MAPPINGS = {
    "mathematics": ("Q001", "Mathematical Sciences", "direct taxonomy match"),
    "physics": ("Q069", "Physics", "direct taxonomy match"),
    "chemistry": (
        "Q003",
        "Chemistry",
        "direct taxonomy match; corrected for page-column extraction order",
    ),
    "biology": ("Q026", "Biology", "cell differentiation biology case"),
    "medicine": ("Q013", "Medicine & Health", "direct medicine and public-health case"),
    "earth_science": (
        "Q109",
        "Ecology",
        "Earth magnetic-field question mapped to earth science",
    ),
    "computer_science": (
        "Q091",
        "Information Science",
        "information science and computer architecture mapping; corrected QID",
    ),
    "materials": (
        "Q089",
        "Engineering & Materials Science",
        "captain-approved materials representative mapping",
    ),
    "astronomy": ("Q046", "Astronomy", "direct taxonomy match"),
    "neuroscience": (
        "Q095",
        "Neuroscience",
        "direct neuroscience case; corrected to the actual Q095 question",
    ),
    "climate": ("Q107", "Ecology", "direct climate semantic match"),
    "engineering": (
        "Q088",
        "Engineering & Materials Science",
        "captain-approved engineering representative mapping",
    ),
}
_RETRYABLE_ERRORS = (TimeoutError, ConnectionError)
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


def load_json(path: Path) -> Any:
    """Load JSON while callers enforce their required object or list schema."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid_json:{path}:{type(error).__name__}") from error
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


def _runtime_execution_gate() -> tuple[bool, list[str], dict[str, str]]:
    """Validate the frozen provider route without exposing credentials or workspace IDs."""
    settings = get_settings()
    provider = str(getattr(settings, "llm_provider", "")).strip()
    model = str(getattr(settings, "qwen_fast_model", "")).strip()
    region = str(getattr(settings, "dashscope_region", "")).strip()
    endpoint = str(getattr(settings, "dashscope_base_url", "")).strip()
    workspace_id = str(getattr(settings, "workspace_id", "")).strip()
    expected_endpoint = (
        f"https://{workspace_id}.{region}{EXPECTED_ENDPOINT_SUFFIX}"
        if workspace_id and region
        else ""
    )
    errors: list[str] = []
    if provider != EXPECTED_PROVIDER:
        errors.append("provider_identity")
    if model != EXPECTED_MODEL:
        errors.append("model_identity")
    if region != EXPECTED_REGION:
        errors.append("region_identity")
    if not workspace_id or endpoint != expected_endpoint:
        errors.append("endpoint_identity")
    if getattr(settings, "qwen_configured", False) is not True:
        errors.append("provider_not_configured")
    return (
        not errors,
        errors,
        {
            "provider": provider,
            "model": model,
            "region": region,
            "endpoint_sha256": hashlib.sha256(endpoint.encode("utf-8")).hexdigest(),
        },
    )


def _source_identity(source: dict[str, Any]) -> tuple[Path, str | None]:
    """Resolve only the approved repository-relative formal question source."""
    configured_path = source.get("path")
    if configured_path != FORMAL_QUESTION_SOURCE_PATH:
        return PROJECT_ROOT / FORMAL_QUESTION_SOURCE_PATH, None
    source_path = (PROJECT_ROOT / FORMAL_QUESTION_SOURCE_PATH).resolve()
    if not source_path.is_file():
        return source_path, None
    return source_path, sha256_file(source_path)


def _question_items(source_path: Path) -> dict[str, dict[str, str]]:
    """Load the formal top-level 125-item list into an ID-indexed representation."""
    value = load_json(source_path)
    if not isinstance(value, list):
        raise ValueError("question_source_structure")
    items: dict[str, dict[str, str]] = {}
    for raw_item in value:
        if not isinstance(raw_item, dict):
            raise ValueError("question_source_structure")
        question_id = raw_item.get("id")
        question = raw_item.get("question")
        domain = raw_item.get("domain")
        if not all(isinstance(value, str) and value for value in (question_id, question, domain)):
            raise ValueError("question_source_structure")
        if question_id in items:
            raise ValueError("question_source_duplicate_id")
        items[question_id] = {"question": question, "domain": domain}
    expected_ids = {f"Q{number:03d}" for number in range(1, 126)}
    if set(items) != expected_ids:
        raise ValueError("question_source_qid_coverage")
    return items


def canonical_input_hash(
    question_id: str, question: str, source_domain: str, normalized_domain: str
) -> str:
    """Hash the approved immutable input projection without text normalization."""
    canonical = json.dumps(
        {
            "question_id": question_id,
            "question": question,
            "source_domain": source_domain,
            "normalized_domain": normalized_domain,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _binding_digest(bindings: list[dict[str, str]]) -> str:
    """Return the canonical digest for the ordered, source-derived question bindings."""
    canonical = json.dumps(bindings, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _question_bindings(
    entries: list[Any], source_path: Path
) -> tuple[list[dict[str, str]], list[str]]:
    """Bind every manifest item to its source question text, domain, and canonical hash."""
    errors: list[str] = []
    try:
        source_questions = _question_items(source_path)
    except ValueError as error:
        return [], [str(error)]
    bindings: list[dict[str, str]] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        question_id = item.get("question_id")
        normalized_domain = item.get("normalized_domain")
        source_item = source_questions.get(question_id) if isinstance(question_id, str) else None
        if source_item is None:
            errors.append("question_source_question_id")
            continue
        if not isinstance(normalized_domain, str):
            errors.append("normalized_domain")
            continue
        approved = APPROVED_DOMAIN_MAPPINGS.get(normalized_domain)
        if approved != (question_id, source_item["domain"], item.get("mapping_basis")):
            errors.append("question_source_approved_mapping")
        if item.get("source_domain") != source_item["domain"]:
            errors.append("question_source_domain")
        if item.get("domain") != normalized_domain:
            errors.append("domain_compatibility")
        if item.get("approval_source") != APPROVAL_SOURCE:
            errors.append("approval_source")
        if item.get("question") != source_item["question"]:
            errors.append("question_source_question")
        expected_hash = canonical_input_hash(
            question_id, source_item["question"], source_item["domain"], normalized_domain
        )
        if item.get("canonical_input_hash") != expected_hash:
            errors.append("canonical_input_hash")
        bindings.append(
            {
                "normalized_domain": normalized_domain,
                "question_id": question_id,
                "canonical_input_hash": expected_hash,
            }
        )
    return bindings, errors


def preflight(manifest_path: Path, protocol_path: Path = PROTOCOL_PATH) -> dict[str, Any]:
    """Validate canonical hashes, source identity, provider-safe schema, and domain coverage."""
    protocol = load_json(protocol_path)
    manifest = load_json(manifest_path)
    errors: list[str] = []
    if not isinstance(protocol, dict) or not isinstance(manifest, dict):
        return {"passed": False, "errors": ["invalid_object"], "provider_calls": 0}
    required_domains = protocol.get("required_domains")
    entries = manifest.get("domains")
    if protocol.get("schema_version") != "1.2" or not isinstance(required_domains, list):
        errors.append("protocol_shape")
    if manifest.get("schema_version") != "1.1" or not isinstance(entries, list):
        errors.append("manifest_shape")
        entries = []
    try:
        manifest_sha = canonical_json_sha256(manifest_path)
    except ValueError:
        manifest_sha = ""
    bindings: list[dict[str, str]] = []
    source = manifest.get("question_source")
    if not isinstance(source, dict):
        errors.append("question_source")
    else:
        source_path, observed_sha = _source_identity(source)
        configured_source = os.getenv("SAGE_QUESTIONS_PATH", "").strip()
        effective_source_path = resolve_questions_path().resolve()
        expected_sha = source.get("sha256")
        if configured_source and source_path.resolve() != effective_source_path:
            errors.append("question_source_runtime_binding")
        if (
            source.get("path") != FORMAL_QUESTION_SOURCE_PATH
            or not isinstance(expected_sha, str)
            or expected_sha != FORMAL_QUESTION_SOURCE_SHA256
            or observed_sha != expected_sha
        ):
            errors.append("question_source_sha256")
        if observed_sha is not None:
            resolved_bindings, binding_errors = _question_bindings(entries, source_path)
            bindings = resolved_bindings
            errors.extend(binding_errors)
    domains = [item.get("normalized_domain") for item in entries if isinstance(item, dict)]
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
        "question_source_binding": {
            "source_path": FORMAL_QUESTION_SOURCE_PATH if isinstance(source, dict) else None,
            "resolved_path": str(source_path) if isinstance(source, dict) else None,
            "sha256": observed_sha if isinstance(source, dict) else None,
            "question_bindings_sha256": _binding_digest(bindings),
        },
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


def _load_resume_ledger(
    path: Path, manifest_sha256: str, question_source_binding: dict[str, Any]
) -> dict[str, Any] | None:
    """Load a compatible ledger only when resume was explicitly requested."""
    if not path.is_file():
        return None
    ledger = load_json(path)
    if ledger.get("manifest_sha256") != manifest_sha256:
        raise ValueError("resume_manifest_identity_mismatch")
    if ledger.get("question_source_binding") != question_source_binding:
        raise ValueError("resume_question_source_binding_mismatch")
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


def _ledger_attempt_count(ledger: dict[str, Any]) -> int:
    """Count every persisted attempt so the 24-attempt cap applies across resumes."""
    entries = ledger.get("entries", [])
    if not isinstance(entries, list):
        return 0
    return sum(
        len(item.get("attempts", []))
        for item in entries
        if isinstance(item, dict) and isinstance(item.get("attempts", []), list)
    )


def _validate_call_audits(records: Any) -> tuple[dict[str, Any], list[str]]:
    """Accept only complete, actual fixed-route audits and aggregate token-only cost."""
    if not isinstance(records, list) or not records:
        return {}, ["call_audit_missing"]
    errors: list[str] = []
    total_input = total_output = total_tokens = 0
    request_ids: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            errors.append("call_audit_invalid")
            continue
        if record.get("provider") != "bailian_qwen" or record.get("mock") is not False:
            errors.append("call_audit_provider_identity")
        if record.get("model_name_internal") != EXPECTED_MODEL:
            errors.append("call_audit_model_identity")
        if record.get("status") != "success" or record.get("fallback_used") is not False:
            errors.append("call_audit_status")
        request_id = record.get("request_id")
        if not isinstance(request_id, str) or not request_id.strip() or request_id in request_ids:
            errors.append("call_audit_request_identity")
        else:
            request_ids.add(request_id)
        usage = [record.get(name) for name in ("input_tokens", "output_tokens", "total_tokens")]
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in usage):
            errors.append("call_audit_tokens")
            continue
        if usage[2] != usage[0] + usage[1]:
            errors.append("call_audit_token_total")
            continue
        total_input += usage[0]
        total_output += usage[1]
        total_tokens += usage[2]
    return (
        {
            "provider": "bailian_qwen",
            "model": EXPECTED_MODEL,
            "call_count": len(records),
            "input_tokens": total_input,
            "output_tokens": total_output,
            "total_tokens": total_tokens,
            "cost_usd": None,
            "cost_accounting": "token_only_unpriced",
        },
        sorted(set(errors)),
    )


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
        "schema_version": "1.2",
        "created_at": _utc_now(),
        "mode": "execute" if execute else "preflight-only",
        "mock": mock,
        "attempt_cap": attempt_cap,
        "global_attempt_cap": MAX_ATTEMPT_CAP,
        "global_attempt_count": 0,
        "manifest": str(manifest_path),
        "manifest_sha256": report["manifest_sha256"],
        "manifest_hash_algorithm": report["manifest_hash_algorithm"],
        "question_source_binding": report["question_source_binding"],
        "environment": report["environment"],
        "entries": [],
        "provider_calls": 0,
        "token_count": None,
        "cost_usd": None,
        "stopped": False,
    }
    protocol = load_json(PROTOCOL_PATH)
    authorization = protocol.get("actual_execution_authorization", {})
    if execute and mock:
        report["errors"] = sorted(set([*report["errors"], "formal_execution_rejects_mock"]))
        report["passed"] = False
    if execute:
        authorized = (
            isinstance(authorization, dict)
            and authorization.get("authorized") is True
            and authorization.get("provider") == EXPECTED_PROVIDER
            and authorization.get("model") == EXPECTED_MODEL
            and authorization.get("region") == EXPECTED_REGION
        )
        if mock:
            report["errors"] = sorted(set([*report["errors"], "formal_execution_rejects_mock"]))
            report["passed"] = False
        elif not authorized:
            report["errors"] = sorted(set([*report["errors"], "actual_execution_not_authorized"]))
            report["passed"] = False
        else:
            runtime_ok, runtime_errors, runtime_identity = _runtime_execution_gate()
            report["runtime_identity"] = runtime_identity
            if not runtime_ok:
                report["errors"] = sorted(set([*report["errors"], *runtime_errors]))
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
        previous = _load_resume_ledger(
            ledger_path, report["manifest_sha256"], report["question_source_binding"]
        )
        if previous is not None:
            ledger = previous
            ledger["resumed_at"] = _utc_now()
    ledger["global_attempt_count"] = _ledger_attempt_count(ledger)
    if ledger["global_attempt_count"] > MAX_ATTEMPT_CAP:
        raise ValueError("resume_global_attempt_cap_exceeded")
    completed_questions = _completed_questions(ledger)
    for item in manifest["domains"]:
        if item["question_id"] in completed_questions:
            continue
        entry: dict[str, Any] = {"domain": item["domain"], "question_id": item["question_id"], "attempts": []}
        max_attempts = 1 + (MAX_RETRIES_PER_ENTRY if retry else 0)
        for attempt in range(1, min(attempt_cap, max_attempts) + 1):
            if ledger["global_attempt_count"] >= MAX_ATTEMPT_CAP:
                ledger["entries"].append(entry)
                ledger["stopped"] = True
                ledger["stop_reason"] = "global_attempt_cap_exhausted"
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
            try:
                _, state = run_pipeline_with_state(
                    item["question_id"],
                    mock_mode=mock,
                    use_local_rag=not mock,
                    use_deep_research=not mock,
                    use_open_literature=not mock,
                )
                summary = summarize_calls(state.llm_calls)
                audit_summary, audit_errors = _validate_call_audits(state.llm_calls)
                if audit_errors:
                    raise ValueError(audit_errors[0])
                total_provider_calls += int(audit_summary["call_count"])
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
                        "audit_identity": audit_summary,
                        "token_count": audit_summary["total_tokens"],
                        "cost_usd": audit_summary["cost_usd"],
                    }
                )
                ledger["global_attempt_count"] += 1
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
                ledger["global_attempt_count"] += 1
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
    ledger["global_attempt_count"] = _ledger_attempt_count(ledger)
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
