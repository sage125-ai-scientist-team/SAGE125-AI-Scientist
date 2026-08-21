"""Captain-authorized formal five-question actual run.

Serial execution only. Outputs are written outside the git worktree.
Authorization is fail-closed and no-clobber. This module does not print
secrets, Workspace IDs, Base URLs, or Authorization headers.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from app.core.call_audit import summarize_calls
from app.core.config import Settings, get_settings
from app.exporters.markdown_exporter import export_research_plan_markdown
from app.exporters.pdf_exporter import export_markdown_to_pdf
from app.formal125 import REQUIRED_RESULT_FILES, SIMILARITY_REVIEW_THRESHOLD
from app.formal125.authorization import (
    Formal125AuthorizationError,
    Formal125RunAuthorization,
    compute_authorization_hash,
    require_actual_authorization,
)
from app.formal125.hashes import sha256_canonical_json, sha256_file
from app.formal125.preflight import locate_source_catalog
from app.workflow.quality_gates import _is_question_source, run_all_quality_gates


FORMAL_5_CASE_IDS: tuple[str, ...] = ("Q001", "Q028", "Q050", "Q075", "Q107")
EXPECTED_PROVIDER = "bailian"
MAX_TOTAL_PROVIDER_CALLS = 270
MAX_TOTAL_INPUT_TOKENS = 8_847_360
MAX_TOTAL_OUTPUT_TOKENS = 901_120
PER_QUESTION_WORST_CALLS = 54
MAX_CONCURRENCY = 1
MAX_RETRIES = 1
WARN_RATIO = 0.80
PAUSE_RATIO = 0.90
BASELINE_PROJECT_PROVIDER_CALLS = 6
EXPECTED_LOCKS = {
    "catalog_hash": "3dfe2cee452dda36211ab64d1581c39d0c9bf476401d2cd5bb1febfe5951a402",
    "model_lock_hash": "84d00c01aeb6aef7b9202ee0de19e6192bb3f8e7a417eb156022ff6c4aac26d5",
    "prompt_lock_hash": "5b12d88b01fc18278dc2d90087caf374e8be0a0ab57eb567c37a2b7121d4e8d2",
    "schema_lock_hash": "5c5b1e139321efdfaf5d66e2887f649e11752265393227b0145eb53229dfa21a",
}
LEAK_PATTERNS = (
    re.compile(r"\bWDBC\b", re.IGNORECASE),
    re.compile(r"wisconsin diagnostic breast", re.IGNORECASE),
    re.compile(r"口蹄疫|非洲猪瘟|animal epidemic", re.IGNORECASE),
)
SECRET_PATTERNS = (
    re.compile(r"(?i)(?:api[_-]?key|authorization|bearer|password|secret)\s*[:=]\s*\S+"),
    re.compile(r"(?i)sk-[A-Za-z0-9]{8,}"),
    re.compile(r"(?i)workspace_id\s*[:=]\s*\S+"),
)
PipelineFn = Callable[..., tuple[Any, Any]]
CaseIds = Sequence[str]


class Formal5ActualRunError(RuntimeError):
    """Fail-closed actual-run error."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def git_head(repo_root: Path) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        text=True,
    ).strip()


def dump(obj: Any) -> Any:
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if isinstance(obj, list):
        return [dump(item) for item in obj]
    if isinstance(obj, dict):
        return {key: dump(value) for key, value in obj.items()}
    return obj


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def atomic_write_json(path: Path, payload: Any) -> None:
    encoded = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    assert_no_secrets(encoded)
    atomic_write_text(path, encoded)


def assert_no_secrets(text: str) -> None:
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            raise Formal5ActualRunError("refusing to persist a secret-bearing payload")


def write_no_clobber_json(path: Path, payload: Mapping[str, Any]) -> Path:
    encoded = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    assert_no_secrets(encoded)
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing != json.loads(encoded):
            raise Formal125AuthorizationError(
                f"no-clobber: existing file differs: {path.name}"
            )
        return path
    atomic_write_text(path, encoded)
    return path


def build_authorization_payload(
    *,
    authorization_id: str,
    case_ids: CaseIds,
    producer_git_sha: str,
    output_root: Path,
    expires_at: str,
    created_at: str,
    extra_lock_hashes: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    del producer_git_sha, created_at, extra_lock_hashes
    payload: dict[str, Any] = {
        "authorization_id": authorization_id,
        "authorized_by_role": "captain",
        "authorized_case_ids": list(case_ids),
        "provider": EXPECTED_PROVIDER,
        "model_lock_hash": EXPECTED_LOCKS["model_lock_hash"],
        "prompt_lock_hash": EXPECTED_LOCKS["prompt_lock_hash"],
        "schema_lock_hash": EXPECTED_LOCKS["schema_lock_hash"],
        "catalog_hash": EXPECTED_LOCKS["catalog_hash"],
        "max_total_provider_calls": MAX_TOTAL_PROVIDER_CALLS,
        "max_retries": MAX_RETRIES,
        "max_total_input_tokens": MAX_TOTAL_INPUT_TOKENS,
        "max_total_output_tokens": MAX_TOTAL_OUTPUT_TOKENS,
        "max_concurrency": MAX_CONCURRENCY,
        "output_root": str(output_root),
        "expires_at": expires_at,
    }
    payload["authorization_hash"] = compute_authorization_hash(payload)
    Formal125RunAuthorization.model_validate(payload)
    return payload


def build_captain_receipt(
    *,
    authorization: Mapping[str, Any],
    authorized_by_account: str,
    producer_git_sha: str,
    created_at: str,
    extra_lock_hashes: Mapping[str, str],
) -> dict[str, Any]:
    receipt = {
        "authorization_id": authorization["authorization_id"],
        "authorized_by_role": "captain",
        "authorized_by_account": authorized_by_account,
        "authorized_case_ids": list(authorization["authorized_case_ids"]),
        "provider": authorization["provider"],
        "producer_git_sha": producer_git_sha,
        "created_at": created_at,
        "expires_at": authorization["expires_at"],
        "output_root": authorization["output_root"],
        "max_total_provider_calls": authorization["max_total_provider_calls"],
        "max_retries": authorization["max_retries"],
        "max_total_input_tokens": authorization["max_total_input_tokens"],
        "max_total_output_tokens": authorization["max_total_output_tokens"],
        "max_concurrency": authorization["max_concurrency"],
        "lock_hashes": {
            "catalog_hash": authorization["catalog_hash"],
            "model_lock_hash": authorization["model_lock_hash"],
            "prompt_lock_hash": authorization["prompt_lock_hash"],
            "schema_lock_hash": authorization["schema_lock_hash"],
            **dict(extra_lock_hashes),
        },
        "authorization_hash": authorization["authorization_hash"],
        "authorization_text": "AUTHORIZE_FORMAL_5_REAL_RUN=YES",
    }
    receipt["receipt_sha256"] = sha256_canonical_json(
        {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    )
    return receipt


def install_captain_runtime_env(
    *,
    export_dir: Path,
    questions_path: Path,
    max_retries: int = MAX_RETRIES,
) -> dict[str, bool]:
    """Load captain settings into process env without printing values or paths."""

    candidates: list[Path] = []
    override = str(os.environ.get("SAGE125_CAPTAIN_ENV_FILE", "") or "").strip()
    if override:
        candidates.append(Path(override))
    repo_root = Path(__file__).resolve().parents[2]
    candidates.append(repo_root / ".env")
    candidates.append(Path("D:/SAGE125-AI-Scientist") / ".env")
    env_file = next((path for path in candidates if path.is_file()), None)
    if env_file is None:
        raise Formal5ActualRunError("captain runtime settings file is missing")
    loaded = Settings(_env_file=str(env_file), _env_file_encoding="utf-8")
    os.environ["LLM_PROVIDER"] = "bailian"
    os.environ["DASHSCOPE_REGION"] = loaded.dashscope_region or "cn-beijing"
    os.environ["LLM_MAX_RETRIES"] = str(max_retries)
    os.environ["EXPORT_DIR"] = str(export_dir)
    os.environ["SAGE_QUESTIONS_PATH"] = str(questions_path)
    bundle_root = os.environ.get("SAGE_EVIDENCE_BUNDLE_DIR", "").strip()
    if bundle_root:
        os.environ["SAGE_EVIDENCE_BUNDLE_DIR"] = bundle_root
    os.environ.pop("MOCK_LLM", None)
    os.environ.pop("SAGE_TEST_EXPORT_DIR", None)
    field_map = {
        "DASHSCOPE_API_KEY": loaded.dashscope_api_key,
        "WORKSPACE_ID": loaded.workspace_id,
        "QWEN_FAST_MODEL": loaded.qwen_fast_model,
        "QWEN_BALANCED_MODEL": loaded.qwen_balanced_model,
        "QWEN_STRONG_MODEL": loaded.qwen_strong_model,
        "QWEN_DEEP_RESEARCH_MODEL": loaded.qwen_deep_research_model,
        "EMBEDDING_BACKEND": loaded.embedding_backend,
        "BAILIAN_EMBEDDING_MODEL": loaded.bailian_embedding_model,
        "BAILIAN_RERANK_MODEL": loaded.bailian_rerank_model,
        "OPENALEX_API_KEY": loaded.openalex_api_key,
        "CONTACT_EMAIL": loaded.contact_email,
        "LLM_TIMEOUT_SECONDS": str(loaded.llm_timeout_seconds),
        "LLM_CONNECT_TIMEOUT_SECONDS": str(loaded.llm_connect_timeout_seconds),
        "LLM_MAX_OUTPUT_TOKENS": str(loaded.llm_max_output_tokens),
        "DEEP_RESEARCH_TIMEOUT_SECONDS": str(loaded.deep_research_timeout_seconds),
    }
    for key, value in field_map.items():
        if value:
            os.environ[key] = str(value)
    get_settings.cache_clear()
    settings = get_settings()
    if settings.llm_provider != "bailian":
        raise Formal5ActualRunError("LLM_PROVIDER is not bailian")
    if not settings.qwen_configured:
        raise Formal5ActualRunError("bailian is not configured")
    return {
        "API_KEY_PRESENT": bool(settings.dashscope_api_key),
        "WORKSPACE_ID_PRESENT": bool(settings.workspace_id),
        "QWEN_CONFIGURED": bool(settings.qwen_configured),
        "DEEP_RESEARCH_CONFIGURED": bool(settings.deep_research_configured),
        "MOCK_LLM": False,
    }


def materialize_questions(destination: Path) -> Path:
    source = locate_source_catalog()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(source.read_bytes())
    return destination


def budget_snapshot(
    *,
    calls: int,
    input_tokens: int,
    output_tokens: int,
) -> dict[str, Any]:
    call_ratio = calls / MAX_TOTAL_PROVIDER_CALLS
    in_ratio = input_tokens / MAX_TOTAL_INPUT_TOKENS
    out_ratio = output_tokens / MAX_TOTAL_OUTPUT_TOKENS
    ratio = max(call_ratio, in_ratio, out_ratio)
    if ratio >= 1.0:
        state = "fail_closed"
    elif ratio >= PAUSE_RATIO:
        state = "pause_after_current"
    elif ratio >= WARN_RATIO:
        state = "warning"
    else:
        state = "ok"
    return {
        "used_calls": calls,
        "used_input_tokens": input_tokens,
        "used_output_tokens": output_tokens,
        "max_calls": MAX_TOTAL_PROVIDER_CALLS,
        "max_input_tokens": MAX_TOTAL_INPUT_TOKENS,
        "max_output_tokens": MAX_TOTAL_OUTPUT_TOKENS,
        "ratio": round(ratio, 6),
        "state": state,
        "estimated_cost": "unknown",
    }


def is_auth_failure(exc: BaseException) -> bool:
    text = str(exc)
    status = getattr(exc, "status_code", None)
    name = type(exc).__name__
    return (
        status in {401, 403}
        or name in {"AuthenticationError", "PermissionDeniedError"}
        or "鉴权失败" in text
        or "401" in text
        or "403" in text
    )


def tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[A-Za-z0-9\u4e00-\u9fff]{2,}", text.lower())}


def similarity_ratio(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    sequence = SequenceMatcher(None, left, right).ratio()
    left_tokens = tokenize(left)
    right_tokens = tokenize(right)
    if not left_tokens or not right_tokens:
        return sequence
    jaccard = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
    return max(sequence, jaccard)


def leak_hits(question_id: str, text: str) -> list[str]:
    hits = [pattern.pattern for pattern in LEAK_PATTERNS if pattern.search(text or "")]
    if question_id != "Q028" and re.search(r"\bQ028\b", text or ""):
        hits.append(r"\bQ028\b")
    return hits


def classify_question_status(
    *,
    pipeline_ok: bool,
    required_present: bool,
    blocking_p0: int,
    blocking_p1: int,
    mock_calls: int,
    booklet_contamination: int,
    auth_failed: bool,
    budget_exceeded: bool,
    actual_execution: bool,
    leak_count: int,
) -> str:
    if auth_failed or budget_exceeded:
        return "blocked"
    if not pipeline_ok or not required_present:
        return "failed"
    if (
        blocking_p0
        or blocking_p1
        or mock_calls
        or booklet_contamination
        or actual_execution
        or leak_count
    ):
        return "partial"
    return "succeeded"


def _call_totals(records: list[dict[str, Any]]) -> tuple[int, int, int, int]:
    real = [
        item
        for item in records
        if not item.get("mock") and item.get("provider") in {"bailian_qwen", "dashscope_deepresearch"}
    ]
    calls = len(records)
    real_calls = len(real)
    input_tokens = sum(int(item.get("input_tokens") or 0) for item in records)
    output_tokens = sum(int(item.get("output_tokens") or 0) for item in records)
    return calls, real_calls, input_tokens, output_tokens


def _booklet_count(cards: list[Any]) -> int:
    count = 0
    for card in cards:
        payload = dump(card)
        if isinstance(payload, dict) and _is_question_source(payload):
            count += 1
    return count


def package_question(
    *,
    question_dir: Path,
    question_id: str,
    plan: Any,
    state: Any,
    previous_texts: Mapping[str, str],
    batch_calls: int,
    batch_input: int,
    batch_output: int,
) -> dict[str, Any]:
    question_dir.mkdir(parents=True, exist_ok=True)
    plan_payload = dump(plan) if plan is not None else {}
    evidence = dump(getattr(state, "retrieved_evidence", []) if state is not None else [])
    trace = dump(getattr(state, "agent_trace", []) if state is not None else [])
    records = dump(getattr(state, "llm_calls", []) if state is not None else [])
    if not isinstance(records, list):
        records = []
    pipeline_gates = getattr(state, "quality_gates", {}) if state is not None else {}
    if plan is not None:
        try:
            pipeline_gates = run_all_quality_gates(
                plan,
                getattr(state, "retrieved_evidence", []) if state is not None else [],
                getattr(state, "agent_trace", []) if state is not None else [],
                hypothesis_generation=getattr(state, "hypothesis_generation", None)
                if state is not None
                else None,
                evidence_extraction=getattr(state, "evidence_extraction", None)
                if state is not None
                else None,
            )
        except Exception as exc:
            pipeline_gates = {
                "passed": False,
                "errors": [type(exc).__name__],
                "warnings": [],
                "gates": {},
            }

    md_path = question_dir / "result.md"
    if plan is not None:
        export_research_plan_markdown(plan, md_path)
    elif not md_path.exists():
        md_path.write_text("# Incomplete run\n", encoding="utf-8")
    result_text = md_path.read_text(encoding="utf-8") if md_path.exists() else ""

    json_path = question_dir / "result.json"
    atomic_write_json(json_path, plan_payload or {"question_id": question_id, "incomplete": True})
    atomic_write_json(question_dir / "evidence_cards.json", evidence)
    atomic_write_json(question_dir / "agent_trace.json", trace)

    pdf_path = question_dir / "result.pdf"
    pdf_result = export_markdown_to_pdf(md_path, pdf_path)
    pdf_ok = isinstance(pdf_result, dict) and pdf_result.get("status") == "ok" and pdf_path.exists()
    if not pdf_ok and pdf_path.exists() and pdf_path.stat().st_size == 0:
        pdf_path.unlink()

    calls, real_calls, input_tokens, output_tokens = _call_totals(
        [item for item in records if isinstance(item, dict)]
    )
    mock_calls = sum(
        1
        for item in records
        if isinstance(item, dict) and (item.get("mock") or item.get("provider") == "mock")
    )
    booklet_contamination = _booklet_count(evidence if isinstance(evidence, list) else [])
    leaks = leak_hits(question_id, result_text + json.dumps(plan_payload, ensure_ascii=False))
    similarities = {
        other_id: round(similarity_ratio(result_text, other_text), 4)
        for other_id, other_text in previous_texts.items()
    }
    max_similarity = max(similarities.values()) if similarities else 0.0
    manual_review = max_similarity > SIMILARITY_REVIEW_THRESHOLD
    actual_execution = bool(plan_payload.get("actual_execution")) if plan_payload else False
    request_ids = [
        item.get("request_id")
        for item in records
        if isinstance(item, dict) and item.get("request_id") and not item.get("mock")
    ]
    gate_errors = list(pipeline_gates.get("errors") or [])
    blocking_p0 = 1 if not pipeline_gates.get("passed", False) and gate_errors else 0
    blocking_p1 = 0
    if mock_calls:
        blocking_p0 += 1
    if booklet_contamination:
        blocking_p0 += 1
    if actual_execution:
        blocking_p0 += 1
    if leaks:
        blocking_p1 += 1
    if real_calls and not request_ids:
        blocking_p1 += 1

    validation = {
        "question_id": question_id,
        "pipeline_quality_gates": pipeline_gates,
        "booklet_contamination_count": booklet_contamination,
        "mock_call_count": mock_calls,
        "leak_hits": leaks,
        "similarity": similarities,
        "max_similarity": max_similarity,
        "manual_review_required": manual_review,
        "actual_execution": actual_execution,
        "p0_count": blocking_p0,
        "p1_count": blocking_p1,
        "estimated_cost": "unknown",
    }
    provider_audit = {
        "question_id": question_id,
        "provider": EXPECTED_PROVIDER,
        "run_mode": getattr(state, "run_mode", None) if state is not None else None,
        "summary": summarize_calls([item for item in records if isinstance(item, dict)]),
        "records": records,
        "estimated_cost": "unknown",
        "settled_cost": "unknown",
        "cost_accounting_mode": "token_only",
    }
    atomic_write_json(question_dir / "validation.json", validation)
    atomic_write_json(question_dir / "provider_audit.json", provider_audit)

    hashed_names = [name for name in REQUIRED_RESULT_FILES if name != "checksums.sha256"]
    content_present = all(
        (question_dir / name).is_file() and (question_dir / name).stat().st_size > 0
        for name in hashed_names
        if name != "package_manifest.json"
    )
    status = classify_question_status(
        pipeline_ok=plan is not None and state is not None,
        required_present=content_present,
        blocking_p0=blocking_p0,
        blocking_p1=blocking_p1,
        mock_calls=mock_calls,
        booklet_contamination=booklet_contamination,
        auth_failed=False,
        budget_exceeded=(calls > PER_QUESTION_WORST_CALLS)
        or ((batch_calls + calls) > MAX_TOTAL_PROVIDER_CALLS)
        or ((batch_input + input_tokens) > MAX_TOTAL_INPUT_TOKENS)
        or ((batch_output + output_tokens) > MAX_TOTAL_OUTPUT_TOKENS),
        actual_execution=actual_execution,
        leak_count=len(leaks),
    )
    manifest = {
        "question_id": question_id,
        "status": status,
        "files": [],
        "required_present": False,
        "provider_calls": calls,
        "real_provider_calls": real_calls,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_cost": "unknown",
        "manual_review_required": manual_review,
        "packaged_at": utc_now(),
    }
    atomic_write_json(question_dir / "package_manifest.json", manifest)
    checksum_lines = []
    for name in hashed_names:
        path = question_dir / name
        if path.exists():
            checksum_lines.append(f"{sha256_file(path)}  {name}")
    atomic_write_text(
        question_dir / "checksums.sha256",
        "\n".join(checksum_lines) + ("\n" if checksum_lines else ""),
    )
    present = {
        name: (question_dir / name).is_file() and (question_dir / name).stat().st_size > 0
        for name in REQUIRED_RESULT_FILES
    }
    required_present = all(present.values())
    files = []
    for name in REQUIRED_RESULT_FILES:
        path = question_dir / name
        files.append(
            {
                "name": name,
                "present": present[name],
                "size_bytes": path.stat().st_size if path.exists() else 0,
                "sha256": sha256_file(path) if path.exists() else None,
            }
        )
    if status == "succeeded" and not required_present:
        status = "failed"
    manifest["files"] = files
    manifest["required_present"] = required_present
    manifest["status"] = status
    atomic_write_json(question_dir / "package_manifest.json", manifest)
    checksum_lines = []
    for name in hashed_names:
        path = question_dir / name
        if path.exists():
            checksum_lines.append(f"{sha256_file(path)}  {name}")
    atomic_write_text(
        question_dir / "checksums.sha256",
        "\n".join(checksum_lines) + ("\n" if checksum_lines else ""),
    )
    return {
        "question_id": question_id,
        "status": status,
        "result_text": result_text,
        "calls": calls,
        "real_calls": real_calls,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "validation": validation,
        "manifest": manifest,
        "required_present": required_present,
    }


def empty_batch_manifest(output_root: Path, authorization_hash: str, producer_git_sha: str) -> dict[str, Any]:
    return {
        "batch_id": output_root.name,
        "case_ids": list(FORMAL_5_CASE_IDS),
        "total": 5,
        "status_counts": {
            "succeeded": 0,
            "partial": 0,
            "failed": 0,
            "blocked": 0,
            "pending": 5,
        },
        "questions": {
            question_id: {"status": "pending"} for question_id in FORMAL_5_CASE_IDS
        },
        "authorization_hash": authorization_hash,
        "producer_git_sha": producer_git_sha,
        "provider": EXPECTED_PROVIDER,
        "output_root": str(output_root),
        "updated_at": utc_now(),
        "provider_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "estimated_cost": "unknown",
        "baseline_project_provider_calls": BASELINE_PROJECT_PROVIDER_CALLS,
    }


def update_batch_manifest(
    path: Path,
    *,
    question_id: str,
    packaged: Mapping[str, Any],
    budget: Mapping[str, Any],
) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    questions = dict(payload.get("questions") or {})
    questions[question_id] = {
        "status": packaged["status"],
        "provider_calls": packaged["calls"],
        "input_tokens": packaged["input_tokens"],
        "output_tokens": packaged["output_tokens"],
        "manual_review_required": packaged["validation"]["manual_review_required"],
        "required_present": packaged["required_present"],
    }
    counts = {"succeeded": 0, "partial": 0, "failed": 0, "blocked": 0, "pending": 0}
    for item in FORMAL_5_CASE_IDS:
        status = str((questions.get(item) or {}).get("status") or "pending")
        counts[status] = counts.get(status, 0) + 1
    payload.update(
        {
            "questions": questions,
            "status_counts": counts,
            "total": 5,
            "updated_at": utc_now(),
            "provider_calls": budget["used_calls"],
            "input_tokens": budget["used_input_tokens"],
            "output_tokens": budget["used_output_tokens"],
            "budget": budget,
            "estimated_cost": "unknown",
        }
    )
    atomic_write_json(path, payload)
    return payload


def default_pipeline(question_id: str, **kwargs: Any) -> tuple[Any, Any]:
    from app.workflow.pipeline import run_pipeline_with_state

    return run_pipeline_with_state(
        question_id=question_id,
        mock_mode=False,
        use_local_rag=True,
        use_deep_research=True,
        use_open_literature=True,
        reviewer_auto_revision=True,
        **kwargs,
    )


def run_formal_five_actual(
    *,
    repo_root: Path,
    output_root: Path,
    authorization_path: Path,
    execute: bool,
    resume: bool = False,
    pipeline_fn: PipelineFn | None = None,
    install_runtime: bool = True,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    auth_dir = output_root / "authorization"
    audit_dir = output_root / "audit"
    auth_dir.mkdir(parents=True, exist_ok=True)
    audit_dir.mkdir(parents=True, exist_ok=True)
    if not execute:
        raise Formal5ActualRunError("dry-run is not an actual run")
    auth = require_actual_authorization(authorization_path)
    if tuple(auth.authorized_case_ids) != FORMAL_5_CASE_IDS:
        raise Formal125AuthorizationError("authorized_case_ids must be the frozen five")
    if auth.provider != EXPECTED_PROVIDER:
        raise Formal125AuthorizationError("provider must be bailian")
    if auth.max_concurrency != 1 or auth.max_retries != 1:
        raise Formal125AuthorizationError("concurrency/retries lock mismatch")
    if auth.max_total_provider_calls > MAX_TOTAL_PROVIDER_CALLS:
        raise Formal125AuthorizationError("call cap exceeds frozen worst-case")
    questions_path = output_root / "input" / "questions_125.json"
    questions_path.parent.mkdir(parents=True, exist_ok=True)
    materialize_questions(questions_path)
    export_dir = output_root / "pipeline_exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    runtime = None
    if install_runtime:
        runtime = install_captain_runtime_env(
            export_dir=export_dir,
            questions_path=questions_path,
            max_retries=auth.max_retries,
        )
    producer = git_head(repo_root)
    manifest_path = output_root / "manifest.json"
    if not manifest_path.exists() or not resume:
        atomic_write_json(
            manifest_path,
            empty_batch_manifest(output_root, auth.authorization_hash, producer),
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    previous_texts: dict[str, str] = {}
    batch_calls = 0
    batch_input = 0
    batch_output = 0
    stop_batch = False
    stop_reason = None
    runner = pipeline_fn or default_pipeline
    for question_id in FORMAL_5_CASE_IDS:
        question_dir = output_root / question_id
        existing_status = str((manifest.get("questions") or {}).get(question_id, {}).get("status") or "pending")
        if resume and existing_status in {"succeeded", "partial", "failed", "blocked"}:
            result_md = question_dir / "result.md"
            if result_md.exists():
                previous_texts[question_id] = result_md.read_text(encoding="utf-8")
            batch_calls += int((manifest.get("questions") or {}).get(question_id, {}).get("provider_calls") or 0)
            batch_input += int((manifest.get("questions") or {}).get(question_id, {}).get("input_tokens") or 0)
            batch_output += int((manifest.get("questions") or {}).get(question_id, {}).get("output_tokens") or 0)
            continue
        budget = budget_snapshot(calls=batch_calls, input_tokens=batch_input, output_tokens=batch_output)
        atomic_write_json(output_root / "checkpoint.json", {
            "current_question": question_id,
            "status": "blocked" if stop_batch else "running",
            "budget": budget,
            "updated_at": utc_now(),
        })
        if stop_batch or budget["state"] in {"pause_after_current", "fail_closed"}:
            packaged = package_question(
                question_dir=question_dir,
                question_id=question_id,
                plan=None,
                state=None,
                previous_texts=previous_texts,
                batch_calls=batch_calls,
                batch_input=batch_input,
                batch_output=batch_output,
            )
            packaged["status"] = "blocked"
            packaged["manifest"]["status"] = "blocked"
            atomic_write_json(question_dir / "package_manifest.json", packaged["manifest"])
            manifest = update_batch_manifest(
                manifest_path, question_id=question_id, packaged=packaged, budget=budget
            )
            continue
        plan = None
        state = None
        auth_failed = False
        try:
            plan, state = runner(question_id)
        except Exception as exc:
            auth_failed = is_auth_failure(exc)
            failure = {
                "question_id": question_id,
                "error_type": type(exc).__name__,
                "auth_failed": auth_failed,
                "failed_at": utc_now(),
            }
            atomic_write_json(question_dir / "failure_receipt.json", failure)
            if auth_failed:
                stop_batch = True
                stop_reason = "auth_failure"
        packaged = package_question(
            question_dir=question_dir,
            question_id=question_id,
            plan=plan,
            state=state,
            previous_texts=previous_texts,
            batch_calls=batch_calls,
            batch_input=batch_input,
            batch_output=batch_output,
        )
        if auth_failed:
            packaged["status"] = "blocked"
            packaged["manifest"]["status"] = "blocked"
            atomic_write_json(question_dir / "package_manifest.json", packaged["manifest"])
        batch_calls += int(packaged["calls"])
        batch_input += int(packaged["input_tokens"])
        batch_output += int(packaged["output_tokens"])
        budget = budget_snapshot(calls=batch_calls, input_tokens=batch_input, output_tokens=batch_output)
        if budget["state"] == "fail_closed":
            stop_batch = True
            stop_reason = "budget_exhausted"
        elif budget["state"] == "pause_after_current":
            stop_batch = True
            stop_reason = "budget_pause_90"
        previous_texts[question_id] = packaged["result_text"]
        inventory = {
            "question_id": question_id,
            "status": packaged["status"],
            "provider_calls": packaged["calls"],
            "input_tokens": packaged["input_tokens"],
            "output_tokens": packaged["output_tokens"],
            "manual_review_required": packaged["validation"]["manual_review_required"],
            "updated_at": utc_now(),
        }
        atomic_write_json(question_dir / "inventory.json", inventory)
        atomic_write_json(output_root / "provider_inventory.json", {
            "batch_calls": batch_calls,
            "batch_input_tokens": batch_input,
            "batch_output_tokens": batch_output,
            "estimated_cost": "unknown",
            "updated_at": utc_now(),
            "baseline_project_provider_calls": BASELINE_PROJECT_PROVIDER_CALLS,
            "project_provider_calls_after": BASELINE_PROJECT_PROVIDER_CALLS + batch_calls,
        })
        atomic_write_json(output_root / "budget_live.json", budget)
        manifest = update_batch_manifest(
            manifest_path, question_id=question_id, packaged=packaged, budget=budget
        )
        atomic_write_json(output_root / "checkpoint.json", {
            "current_question": question_id,
            "status": packaged["status"],
            "budget": budget,
            "stop_reason": stop_reason,
            "updated_at": utc_now(),
        })
    counts = manifest.get("status_counts") or {}
    finished = sum(int(counts.get(key) or 0) for key in ("succeeded", "partial", "failed", "blocked"))
    if finished != 5:
        raise Formal5ActualRunError("manifest status_counts must sum to 5")
    if int(counts.get("succeeded") or 0) == 5:
        batch_status = "PASS"
    elif int(counts.get("succeeded") or 0) > 0:
        batch_status = "PASS_WITH_PARTIAL_QUESTIONS"
    else:
        batch_status = "FAIL"
    summary = {
        "batch_status": batch_status,
        "status_counts": counts,
        "provider_calls": batch_calls,
        "input_tokens": batch_input,
        "output_tokens": batch_output,
        "estimated_cost": "unknown",
        "stop_reason": stop_reason,
        "runtime_present": runtime,
        "producer_git_sha": producer,
        "authorization_hash": auth.authorization_hash,
        "project_provider_calls_before": BASELINE_PROJECT_PROVIDER_CALLS,
        "project_provider_calls_after": BASELINE_PROJECT_PROVIDER_CALLS + batch_calls,
        "completed_at": utc_now(),
    }
    atomic_write_json(output_root / "summary.json", summary)
    return summary


def write_captain_authorization(
    *,
    repo_root: Path,
    output_root: Path,
    authorization_id: str | None = None,
    expires_hours: int = 72,
) -> dict[str, Any]:
    created_at = utc_now()
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=expires_hours)).isoformat()
    producer = git_head(repo_root)
    auth_id = authorization_id or f"formal5-actual-{output_root.name}"
    extra = {
        "domain_map_sha256": "d45bb65ce4d2620d2c91c7a7cb7eb44dd186be3b7ce7d71a1acbca03c92ed75a",
        "gate_policy_sha256": "ffb1e770da87b7bee9fc6aa67e9d6e53ab73fcd47af64cc91e220ac4f4afb1a3",
        "batch_policy_sha256": "aa1e7cc2d1799956eb014018a03e7cd58424eef67017da0d434d708b3a0fbac1",
        "formal_5_selection_sha256": "d03d40b32ecaccdd9736d0ff334da762b9a4858812c70028c01d2c90cc6f25f7",
    }
    payload = build_authorization_payload(
        authorization_id=auth_id,
        case_ids=FORMAL_5_CASE_IDS,
        producer_git_sha=producer,
        output_root=output_root,
        expires_at=expires_at,
        created_at=created_at,
        extra_lock_hashes=extra,
    )
    auth_dir = output_root / "authorization"
    auth_path = auth_dir / "authorization.json"
    write_no_clobber_json(auth_path, payload)
    receipt = build_captain_receipt(
        authorization=payload,
        authorized_by_account="liuyanbo12",
        producer_git_sha=producer,
        created_at=created_at,
        extra_lock_hashes=extra,
    )
    write_no_clobber_json(auth_dir / "captain_authorization_receipt.json", receipt)
    require_actual_authorization(auth_path)
    return {
        "authorization_path": str(auth_path),
        "authorization_hash": payload["authorization_hash"],
        "receipt_sha256": receipt["receipt_sha256"],
        "producer_git_sha": producer,
        "expires_at": expires_at,
    }
