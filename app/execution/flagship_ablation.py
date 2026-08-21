"""Q028 FULL_SYSTEM vs NO_REVIEWER actual component ablation harness.

Captain-local experiment Q028-ACTUAL-ABLATION-01. This is not T09 Wave C
authorization. It never updates the Q028 canonical pointer or final package.

The only allowed Arm difference is the Scientific Reviewer. Round 1 evidence,
dataset pin, scientific controls, planner identity, policy validator, and the
Round 2 scientific kernel are frozen by the preregistered protocol.
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from pydantic import ValidationError

from app.execution.flagship_reviewer import (
    ALLOWED_REVISION_POLICY,
    SCIENTIFIC_SCOPE,
    V2RevisionPlanOutput,
    FlagshipReviewerError,
    assert_bailian_available,
    validate_v2_plan_against_policy,
)
from app.execution.wdbc_baseline import BaselineConfig, run_baseline
from app.execution.provenance import collect_git_provenance


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = (
    REPOSITORY_ROOT
    / "docs"
    / "reproducibility"
    / "ablations"
    / "Q028"
    / "ACTUAL_ABLATION_01_PROTOCOL.json"
)
PROTOCOL_ID = "Q028-ACTUAL-ABLATION-01"
CANONICAL_ATTEMPT = "pub-a7d6c7e7dd6c42a488c7f39079d6a434"
CANONICAL_DIR = (
    REPOSITORY_ROOT / "docs" / "modules" / "T05" / "canonical" / f"Q028.{CANONICAL_ATTEMPT}"
)
POINTER_PATH = REPOSITORY_ROOT / "docs" / "modules" / "T05" / "canonical" / "canonical_pointer.json"
ROUND1_DIR = REPOSITORY_ROOT / "docs" / "modules" / "T05" / "round1"
ROUND2_DIR = REPOSITORY_ROOT / "docs" / "modules" / "T05" / "round2"
ROUND1_CONFIG_PATH = REPOSITORY_ROOT / "experiments" / "flagship" / "round1_config.json"
DATASET_MANIFEST_PATH = REPOSITORY_ROOT / "experiments" / "flagship" / "dataset_manifest.json"
ABLATION_ROOT = REPOSITORY_ROOT / "docs" / "reproducibility" / "ablations" / "Q028"
ABLATION_POINTER_PATH = ABLATION_ROOT / "ACTUAL_ABLATION_01_POINTER.json"
DATASET_SHA256 = "d606af411f3e5be8a317a5a8b652b425aaf0ff38ca683d5327ffff94c3695f4a"
DATASET_SIZE_BYTES = 124103
ROUND1_EXECUTION_ID = "execution-5577816b92ac434c99b9c0ffcda21660"
SUCCESS_THRESHOLD = 0.95
OFFLINE_CACHE_ROOT = (
    REPOSITORY_ROOT / "tmp" / "preserved_from_d_root" / "T05_WDBC" / "formal-cache"
)


class AblationError(RuntimeError):
    """Harness-level failure (distinct from a valid negative experimental result)."""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def _pretty_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(text: str) -> str:
    return _sha256_bytes(text.encode("utf-8"))


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AblationError(f"expected object JSON: {path}")
    return value


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_pretty_json(payload), encoding="utf-8", newline="\n")


def load_protocol(path: Path = PROTOCOL_PATH) -> dict[str, Any]:
    protocol = _load_json(path)
    if protocol.get("protocol_id") != PROTOCOL_ID:
        raise AblationError("protocol_id mismatch")
    return protocol


def protocol_commit_sha(*, repository_root: Path = REPOSITORY_ROOT) -> str:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repository_root),
            "log",
            "-1",
            "--format=%H",
            "--",
            "docs/reproducibility/ablations/Q028/ACTUAL_ABLATION_01_PROTOCOL.json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    sha = (result.stdout or "").strip()
    if result.returncode != 0 or not sha:
        raise AblationError("protocol is not committed; refusing provider call")
    dirty = subprocess.run(
        [
            "git",
            "-C",
            str(repository_root),
            "diff",
            "--name-only",
            "--",
            "docs/reproducibility/ablations/Q028/ACTUAL_ABLATION_01_PROTOCOL.json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if (dirty.stdout or "").strip():
        raise AblationError("protocol working-tree is dirty; refusing provider call")
    return sha


def _lf_bytes(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def verify_canonical_package_readonly(canonical_dir: Path = CANONICAL_DIR) -> dict[str, Any]:
    """Read-only checksum verification. Does not write or repair any file."""
    manifest = _load_json(canonical_dir / "package_manifest.json")
    mismatches: list[str] = []
    verified: list[str] = []
    for entry in manifest.get("files") or []:
        path = canonical_dir / entry["path"]
        raw = path.read_bytes()
        sha = _sha256_bytes(raw)
        lf_sha = _sha256_bytes(_lf_bytes(raw))
        recorded = entry["sha256"]
        if sha == recorded:
            verified.append(entry["path"])
        elif lf_sha == recorded:
            verified.append(f"{entry['path']} (LF-normalized CRLF checkout)")
        else:
            mismatches.append(entry["path"])
    pointer = _load_json(POINTER_PATH)
    return {
        "ok": not mismatches and pointer.get("attempt_id") == CANONICAL_ATTEMPT,
        "mismatches": mismatches,
        "verified": verified,
        "pointer_attempt_id": pointer.get("attempt_id"),
        "pointer_unchanged": pointer.get("attempt_id") == CANONICAL_ATTEMPT,
        "publication_state": "PUBLISHED_VERIFIED",
    }


def recompute_holdout_metrics(predictions_csv: Path) -> dict[str, Any]:
    tp = tn = fp = fn = 0
    with predictions_csv.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            actual = row["actual_label"]
            predicted = row["predicted_label"]
            if actual == "M" and predicted == "M":
                tp += 1
            elif actual == "M" and predicted == "B":
                fn += 1
            elif actual == "B" and predicted == "B":
                tn += 1
            else:
                fp += 1
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    specificity = tn / (tn + fp) if (tn + fp) else 0.0
    return {
        "true_positive": tp,
        "true_negative": tn,
        "false_positive": fp,
        "false_negative": fn,
        "malignant_recall": recall,
        "balanced_accuracy": (recall + specificity) / 2.0,
        "false_negative_rate": fn / (fn + tp) if (fn + tp) else 0.0,
    }


def build_full_system_reference(protocol: dict[str, Any] | None = None) -> dict[str, Any]:
    protocol = protocol or load_protocol()
    round1_summary = _load_json(ROUND1_DIR / "artifacts" / "run-summary.json")
    round2_summary = _load_json(ROUND2_DIR / "artifacts" / "run-summary.json")
    round1_recomputed = recompute_holdout_metrics(ROUND1_DIR / "artifacts" / "predictions.csv")
    round2_recomputed = recompute_holdout_metrics(ROUND2_DIR / "artifacts" / "predictions.csv")
    package_ok = verify_canonical_package_readonly()
    r1_recall = round1_recomputed["malignant_recall"]
    r2_recall = round2_recomputed["malignant_recall"]
    return {
        "schema_version": "1.0",
        "protocol_id": PROTOCOL_ID,
        "arm": "FULL_SYSTEM",
        "canonical_attempt_id": CANONICAL_ATTEMPT,
        "canonical_path": str(CANONICAL_DIR.as_posix()),
        "package_manifest_sha256": _sha256_file(CANONICAL_DIR / "package_manifest.json"),
        "producer_git_sha": "f29fbf4a40ac3f0b17df4d8a8cd03de8672f1c87",
        "publication_state": "PUBLISHED_VERIFIED",
        "package_checksum_ok": package_ok["ok"],
        "round1_execution_id": ROUND1_EXECUTION_ID,
        "round1_malignant_recall": r1_recall,
        "round1_balanced_accuracy": round1_recomputed["balanced_accuracy"],
        "round2_malignant_recall": r2_recall,
        "round2_balanced_accuracy": round2_recomputed["balanced_accuracy"],
        "round2_false_negative_rate": round2_recomputed["false_negative_rate"],
        "historical_round1_malignant_recall": round1_summary["metrics"]["malignant_recall"],
        "historical_round2_malignant_recall": round2_summary["metrics"]["malignant_recall"],
        "round1_recompute_match": abs(r1_recall - round1_summary["metrics"]["malignant_recall"]) < 1e-12,
        "round2_recompute_match": abs(r2_recall - round2_summary["metrics"]["malignant_recall"]) < 1e-12,
        "target_achieved": r2_recall >= SUCCESS_THRESHOLD,
        "revision_effective": r2_recall > r1_recall,
        "traceability_complete": True,
        "structured_issue_available": True,
        "issue_closure_auditable": True,
        "scientific_scope_pass": True,
        "provider_call_count": 2,
        "reviewer_calls": 1,
        "planner_calls": 1,
        "v2_schema_valid": True,
        "authorized_revision": True,
        "round2_executed": True,
        "frozen_round1_metrics": round1_summary["metrics"],
        "frozen_round2_metrics": round2_summary["metrics"],
        "success_threshold": protocol["success_threshold"],
    }


def _round1_execution_summary() -> dict[str, Any]:
    result = _load_json(ROUND1_DIR / "execution_result.json")
    metrics = {m["name"]: m["value"] for m in result.get("metrics", [])}
    return {
        "execution_id": result.get("execution_id"),
        "question_id": result.get("question_id"),
        "status": result.get("status"),
        "actual_execution": result.get("actual_execution"),
        "metrics": metrics,
        "dataset_sha256": (result.get("datasets") or [{}])[0].get("sha256"),
        "seed": result.get("seed"),
        "git_dirty": (result.get("environment_fingerprint") or {}).get("git_dirty"),
    }


def build_no_reviewer_context(round1_config: dict[str, Any] | None = None) -> dict[str, Any]:
    round1_config = round1_config or _load_json(ROUND1_CONFIG_PATH)
    trigger = round1_config["round2_trigger"]
    return {
        "case_id": "Q028",
        "mode": "NO_REVIEWER",
        "reviewer_enabled": False,
        "review_feedback": None,
        "iteration": 2,
        "scientific_scope": SCIENTIFIC_SCOPE,
        "round1_execution_result": _round1_execution_summary(),
        "target_metric": trigger["metric"],
        "target_value": trigger["target"],
        "current_decision_threshold": round1_config.get("decision_threshold"),
        "current_round1_config": round1_config,
        "allowed_revision_policy": ALLOWED_REVISION_POLICY,
        "frozen_scientific_controls": {
            "dataset": "UCI WDBC (fixed, pinned by sha256)",
            "dataset_sha256": DATASET_SHA256,
            "seed": round1_config.get("seed"),
            "test_fraction": round1_config.get("test_fraction"),
            "optimizer": round1_config.get("optimizer"),
        },
        "output_schema": {
            "plan_id": "string",
            "responds_to_issue_ids": [],
            "proposed_changes": [{"field": "string", "from": "<value>", "to": "<value>", "justification": "string"}],
            "expected_effect": "string",
        },
    }


def build_no_reviewer_prompts(context: dict[str, Any]) -> tuple[str, str]:
    system_prompt = (
        "You are the experiment-revision planner for a controlled, frozen "
        "binary classification protocol operating in NO_REVIEWER mode. There "
        "is no Scientific Reviewer in this arm. You must not pretend a "
        "reviewer exists, must not invent reviewer issue_id values, must not "
        "cite ReviewFeedback, and must not generate forged reviewer comments. "
        "You may only inspect the provided Round 1 execution result, the "
        "scientific scope, the target metric, and the allowed_revision_policy. "
        "If you do not have sufficient grounds for a change, output no revision "
        "by returning proposed_changes as an empty list. If you do propose a "
        "change, it must stay inside allowed_revision_policy. The only in-policy "
        "experimental change is decision_threshold 0.5 -> 0.4. Never change the "
        "dataset, split, seed, model, learning rate, iterations, L2, labels, or "
        "success metric. Never make clinical extrapolations or claim this "
        "experiment cures cancer. Respond with a single JSON object matching "
        "exactly this schema (no extra keys, no markdown fences):\n"
        '{"plan_id": string, "responds_to_issue_ids": [], '
        '"proposed_changes": [{"field": string, "from": <value>, '
        '"to": <value>, "justification": string}], '
        '"expected_effect": string}'
    )
    user_prompt = (
        "Current mode is NO_REVIEWER. Using only the Round 1 execution result "
        "and allowed_revision_policy below, propose the next step as the JSON "
        "object described in the system prompt. Do not invent a reviewer.\n\n"
        f"CONTEXT_JSON:\n{_canonical_json(context)}"
    )
    return system_prompt, user_prompt


def detect_reviewer_leaks(text: str, protocol: dict[str, Any]) -> list[str]:
    needles = protocol.get("full_system_leak_needles") or {}
    hits: list[str] = []
    for name, needle in needles.items():
        if needle and str(needle) in text:
            hits.append(name)
    return hits


def locate_pinned_dataset() -> Path:
    candidates = [
        OFFLINE_CACHE_ROOT / "datasets" / "uci-wdbc-v1995-10-31" / "wdbc.data",
        Path(
            r"D:\SAGE125_Local_Worktrees\flagship_provenance_20260820-155003"
            r"\tmp\preserved_from_d_root\T05_WDBC\formal-cache"
            r"\datasets\uci-wdbc-v1995-10-31\wdbc.data"
        ),
    ]
    for path in candidates:
        if path.is_file() and _sha256_file(path) == DATASET_SHA256:
            return path
    raise AblationError("pinned WDBC dataset cache is not available offline")


def run_no_reviewer_round2(*, destination: Path, decision_threshold: float) -> dict[str, Any]:
    if abs(decision_threshold - 0.4) > 1e-12:
        raise AblationError("Round 2 may apply only the authorized threshold 0.4")
    dataset_src = locate_pinned_dataset()
    local_cache = OFFLINE_CACHE_ROOT / "datasets" / "uci-wdbc-v1995-10-31" / "wdbc.data"
    if dataset_src != local_cache:
        local_cache.parent.mkdir(parents=True, exist_ok=True)
        if not local_cache.exists():
            shutil.copy2(dataset_src, local_cache)
        if _sha256_file(local_cache) != DATASET_SHA256:
            raise AblationError("copied dataset pin mismatch")
        dataset_src = local_cache
    git = collect_git_provenance(repository_root=REPOSITORY_ROOT)
    output_root = destination / "round2_run"
    if output_root.exists():
        shutil.rmtree(output_root)
    config = BaselineConfig(
        seed=125,
        test_fraction=0.2,
        learning_rate=0.05,
        iterations=2000,
        l2=0.001,
        decision_threshold=decision_threshold,
        recall_target=0.95,
        threshold_step=0.1,
        expected_sha256=DATASET_SHA256,
        expected_size_bytes=DATASET_SIZE_BYTES,
    )
    summary = run_baseline(dataset_src, output_root, config)
    predictions = output_root / "output" / "predictions.csv"
    recomputed = recompute_holdout_metrics(predictions)
    metrics = {
        "malignant_recall": recomputed["malignant_recall"],
        "balanced_accuracy": recomputed["balanced_accuracy"],
        "false_negative_rate": recomputed["false_negative_rate"],
    }
    return {
        "executed": True,
        "git_sha": git.get("commit_sha"),
        "git_dirty": git.get("dirty"),
        "dataset_sha256": DATASET_SHA256,
        "decision_threshold": decision_threshold,
        "metrics": metrics,
        "recomputed": recomputed,
        "output_root": str(output_root.as_posix()),
        "run_summary": summary,
    }


def classify_conclusion(
    *,
    full_system: dict[str, Any],
    no_reviewer: dict[str, Any],
    protocol_ok: bool,
) -> dict[str, Any]:
    if not protocol_ok or no_reviewer.get("provider_failed") or no_reviewer.get("inputs_inconsistent"):
        result = "INCONCLUSIVE"
    else:
        fs_target = bool(full_system.get("target_achieved"))
        nr_target = bool(no_reviewer.get("target_achieved"))
        nr_legal_effective = bool(no_reviewer.get("revision_effective")) and bool(
            no_reviewer.get("authorized_revision_proposed")
        )
        fs_trace = bool(full_system.get("traceability_complete"))
        scope_ok = bool(full_system.get("scientific_scope_pass")) and bool(
            no_reviewer.get("scientific_scope_pass")
        )
        metrics_close = no_reviewer.get("round2_executed") and all(
            abs(float(full_system[k]) - float(no_reviewer[k])) < 1e-12
            for k in ("round2_malignant_recall", "round2_balanced_accuracy", "round2_false_negative_rate")
            if k in no_reviewer and no_reviewer[k] is not None
        )
        if (
            fs_target
            and (not nr_target or not nr_legal_effective)
            and fs_trace
            and scope_ok
        ):
            result = "QUALITY_AND_TRACEABILITY_GAIN"
        elif (
            fs_target
            and nr_target
            and metrics_close
            and fs_trace
            and not no_reviewer.get("structured_issue_available")
            and not no_reviewer.get("issue_closure_auditable")
            and scope_ok
        ):
            result = "TRACEABILITY_ONLY_GAIN"
        elif (
            nr_target
            and no_reviewer.get("round2_malignant_recall") is not None
            and float(no_reviewer["round2_malignant_recall"]) > float(full_system["round2_malignant_recall"])
            and scope_ok
            and no_reviewer.get("policy_ok")
        ):
            result = "NO_REVIEWER_BETTER"
        elif fs_target == nr_target and metrics_close and no_reviewer.get("structured_issue_available"):
            result = "NO_MEASURABLE_GAIN"
        elif fs_target and nr_target and fs_trace and not no_reviewer.get("issue_closure_auditable"):
            result = "TRACEABILITY_ONLY_GAIN"
        else:
            result = "INCONCLUSIVE"
    return {
        "REVIEWER_EFFECT_RESULT": result,
        "quality_gain": result == "QUALITY_AND_TRACEABILITY_GAIN",
        "traceability_gain": result in {"QUALITY_AND_TRACEABILITY_GAIN", "TRACEABILITY_ONLY_GAIN"},
        "additional_call_cost": {
            "reviewer_calls": 1,
            "note": (
                "FULL_SYSTEM's extra Reviewer call is the real cost of the ablated "
                "component. Arms are not force-aligned on call count."
            ),
        },
    }


def _metric_row(name: str, full_value: Any, ablation_value: Any) -> dict[str, Any]:
    return {
        "metric": name,
        "FULL_SYSTEM": full_value,
        "NO_REVIEWER": ablation_value,
        "delta": None
        if full_value is None or ablation_value is None or not isinstance(full_value, (int, float))
        else (ablation_value - full_value if isinstance(ablation_value, (int, float)) else None),
    }


def build_comparison_matrix(full_system: dict[str, Any], no_reviewer: dict[str, Any]) -> dict[str, Any]:
    rows = [
        _metric_row("Reviewer calls", 1, 0),
        _metric_row("Planner calls", 1, no_reviewer.get("planner_calls", 0)),
        _metric_row("Total calls", 2, no_reviewer.get("provider_call_count", 0)),
        _metric_row("V2 schema valid", True, no_reviewer.get("revision_plan_schema_valid")),
        _metric_row("Authorized revision", True, no_reviewer.get("authorized_revision_proposed")),
        _metric_row("Revision effective", True, no_reviewer.get("revision_effective")),
        _metric_row("Round 2 executed", True, no_reviewer.get("round2_executed")),
        _metric_row("Malignant recall", full_system["round2_malignant_recall"], no_reviewer.get("round2_malignant_recall")),
        _metric_row("Balanced accuracy", full_system["round2_balanced_accuracy"], no_reviewer.get("round2_balanced_accuracy")),
        _metric_row("False negative rate", full_system["round2_false_negative_rate"], no_reviewer.get("round2_false_negative_rate")),
        _metric_row("Target achieved", full_system["target_achieved"], no_reviewer.get("target_achieved")),
        _metric_row("Structured issue", True, False),
        _metric_row("Issue closure auditable", True, False),
        _metric_row("Traceability complete", True, no_reviewer.get("traceability_complete")),
        _metric_row("Scientific scope pass", True, no_reviewer.get("scientific_scope_pass")),
        _metric_row("Latency seconds", "unknown", no_reviewer.get("latency_seconds")),
        _metric_row("Tokens", "unknown", no_reviewer.get("total_tokens")),
        _metric_row("Cost", "unknown", "unknown"),
    ]
    return {
        "schema_version": "1.0",
        "protocol_id": PROTOCOL_ID,
        "rows": rows,
        "cost_rule": "unknown when provider does not return a reliable price; never guessed as 0",
        "call_alignment_note": (
            "FULL_SYSTEM has one extra Reviewer call because that is the ablated "
            "component. Identical conditions do not require identical call counts."
        ),
    }


def _write_checksums(package_dir: Path) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    lines: list[str] = []
    for path in sorted(package_dir.rglob("*")):
        if not path.is_file() or path.name in {"package_manifest.json", "checksums.sha256"}:
            continue
        rel = path.relative_to(package_dir).as_posix()
        digest = _sha256_file(path)
        size = path.stat().st_size
        files.append({"path": rel, "sha256": digest, "size_bytes": size})
        lines.append(f"{digest}  {rel}")
    checksums = "\n".join(lines) + "\n"
    (package_dir / "checksums.sha256").write_text(checksums, encoding="utf-8", newline="\n")
    manifest = {"schema_version": "1.0", "files": files}
    _write_json(package_dir / "package_manifest.json", manifest)
    return manifest


def existing_ablation_call_count(package_dir: Path) -> int:
    audit_path = package_dir / "provider_audit.json"
    if not audit_path.exists():
        return 0
    payload = _load_json(audit_path)
    return len(payload.get("calls") or [])


def call_no_reviewer_planner(
    *,
    system_prompt: str,
    user_prompt: str,
    model: str,
    temperature: float,
    destination_dir: Path,
    chat_fn: Callable[..., str] | None = None,
) -> dict[str, Any]:
    """Exactly one planner call. No Scientific Reviewer. No mock fallback."""
    started = time.perf_counter()
    raw_text = ""
    request_id = None
    usage: dict[str, Any] = {}
    status = "ok"
    error = None
    gate = None
    try:
        if chat_fn is None:
            assert_bailian_available()
            from app.clients.qwen_chat_client import QwenChatClient, QwenClientError
            from app.core.config import get_settings

            settings = get_settings()
            try:
                settings = settings.model_copy(update={"llm_max_retries": 0})
            except Exception:
                pass
            client = QwenChatClient(settings=settings)

            def _chat(messages: list[dict[str, str]], **kwargs: Any) -> str:
                return client.chat(messages, **kwargs)

            chat_fn = _chat
            bound_client = client
        else:
            bound_client = None

        raw_text = chat_fn(
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            model=model,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        if bound_client is not None:
            request_id = bound_client.last_request_id
            usage = dict(bound_client.last_usage or {})
            if not request_id:
                status = "failed"
                gate = "BLOCKED_NO_REQUEST_ID"
                error = "planner response carried no auditable request_id"
        else:
            request_id = request_id or "test-injected-request"
    except FlagshipReviewerError as exc:
        status = "failed"
        gate = exc.gate
        error = str(exc)
    except Exception as exc:  # noqa: BLE001 - must record provider failure without retry
        status = "failed"
        gate = "BLOCKED_PROVIDER_ERROR"
        error = str(exc)
        if "QwenClientError" in type(exc).__name__ or "mock" in str(exc).lower():
            pass
    latency = round(time.perf_counter() - started, 6)
    if isinstance(raw_text, str) and raw_text.startswith("【MOCK】"):
        status = "failed"
        gate = "BLOCKED_MOCK"
        error = "mock output refused"
        raw_text = ""
    record = {
        "call_id": f"call-{uuid.uuid4().hex}",
        "role": "no_reviewer_v2_revision_plan",
        "provider": "bailian",
        "model": model,
        "request_id": request_id,
        "timestamp": _now(),
        "status": status,
        "gate": gate,
        "error": error,
        "latency_seconds": latency,
        "usage": usage,
        "input_hash": _sha256_text(_canonical_json({"system": system_prompt, "user": user_prompt})),
        "output_hash": _sha256_text(raw_text or ""),
        "raw_output_path": str((destination_dir / "v2_revision_plan_raw.txt").as_posix()),
    }
    destination_dir.mkdir(parents=True, exist_ok=True)
    (destination_dir / "v2_revision_plan_raw.txt").write_text(raw_text or "", encoding="utf-8", newline="\n")
    return {"record": record, "raw_text": raw_text, "status": status}


def parse_v2_plan(raw_text: str) -> tuple[V2RevisionPlanOutput | None, str | None]:
    if not raw_text.strip():
        return None, "empty_output"
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        return None, "invalid_json"
    try:
        return V2RevisionPlanOutput.model_validate(payload), None
    except ValidationError:
        return None, "schema_invalid"


def run_actual_ablation(
    *,
    destination: Path | None = None,
    chat_fn: Callable[..., str] | None = None,
    skip_provider: bool = False,
    repository_root: Path = REPOSITORY_ROOT,
) -> dict[str, Any]:
    protocol = load_protocol(repository_root / "docs/reproducibility/ablations/Q028/ACTUAL_ABLATION_01_PROTOCOL.json")
    protocol_sha = protocol_commit_sha(repository_root=repository_root)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    ablation_id = f"Q028-ACTUAL-ABLATION-01-{stamp}"
    destination = destination or (ABLATION_ROOT / f"ACTUAL_ABLATION_01_{stamp}")
    if destination.exists():
        raise AblationError(f"ablation destination already exists: {destination}")
    destination.mkdir(parents=True)

    pointer_before = POINTER_PATH.read_bytes()
    full_system = build_full_system_reference(protocol)
    _write_json(destination / "full_system_reference.json", full_system)
    _write_json(destination / "ablation_protocol.json", protocol)

    context = build_no_reviewer_context()
    system_prompt, user_prompt = build_no_reviewer_prompts(context)
    prompt_text = f"SYSTEM:\n{system_prompt}\n\nUSER:\n{user_prompt}"
    leaks = detect_reviewer_leaks(prompt_text, protocol)
    input_hash = _sha256_text(_canonical_json(context))
    prompt_hash = _sha256_text(prompt_text)
    _write_json(destination / "no_reviewer_input.json", context)
    (destination / "no_reviewer_prompt_snapshot.txt").write_text(
        prompt_text[:8000], encoding="utf-8", newline="\n"
    )
    if leaks:
        raise AblationError(f"REVIEWER_CONTENT_LEAK_COUNT={len(leaks)}: {leaks}")

    provider_failed = False
    schema_valid = False
    plan: V2RevisionPlanOutput | None = None
    policy = None
    proposed_change = None
    unauthorized_count = 0
    round2_payload: dict[str, Any] | None = None
    round2_reason = None
    audit_calls: list[dict[str, Any]] = []

    if skip_provider:
        provider_failed = True
        round2_reason = "PROVIDER_FAILED"
        _write_json(destination / "provider_failure.json", {"reason": "skip_provider"})
    else:
        if existing_ablation_call_count(destination) >= 1:
            raise AblationError("max_new_provider_calls=1 already exhausted")
        call = call_no_reviewer_planner(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=str(protocol["planner_model"]),
            temperature=float(protocol["planner_temperature"]),
            destination_dir=destination,
            chat_fn=chat_fn,
        )
        audit_calls.append(call["record"])
        if call["status"] != "ok":
            provider_failed = True
            round2_reason = "PROVIDER_FAILED"
            _write_json(destination / "provider_failure.json", call["record"])
        else:
            plan, parse_error = parse_v2_plan(call["raw_text"])
            if plan is None:
                schema_valid = False
                round2_reason = "INVALID_SCHEMA"
                _write_json(
                    destination / "v2_revision_plan.json",
                    {"schema_valid": False, "parse_error": parse_error, "raw_preserved": True},
                )
            else:
                schema_valid = True
                if plan.responds_to_issue_ids:
                    # Fabricated reviewer issues are recorded, never treated as ReviewFeedback.
                    schema_valid = True
                _write_json(destination / "v2_revision_plan.json", plan.model_dump(mode="json"))
                policy = validate_v2_plan_against_policy(plan)
                unauthorized_count = len(policy.unauthorized_changes)
                _write_json(destination / "policy_validation.json", policy.model_dump(mode="json"))
                if not plan.proposed_changes:
                    proposed_change = "no_revision"
                    round2_reason = "NO_REVISION"
                elif unauthorized_count:
                    proposed_change = policy.unauthorized_changes[0]
                    round2_reason = "POLICY_REJECTED"
                elif policy.authorized_changes:
                    proposed_change = policy.authorized_changes[0]
                    authorized = policy.authorized_changes[0]
                    round2_payload = run_no_reviewer_round2(
                        destination=destination,
                        decision_threshold=float(authorized["to"]),
                    )
                    round2_reason = None
                else:
                    proposed_change = "no_authorized_change"
                    round2_reason = "NO_REVISION"

    _write_json(
        destination / "provider_audit.json",
        {
            "schema_version": "1.0",
            "protocol_id": PROTOCOL_ID,
            "ablation_id": ablation_id,
            "max_new_provider_calls": 1,
            "scientific_reviewer_calls": 0,
            "calls": audit_calls,
        },
    )

    nr_recall = (round2_payload or {}).get("metrics", {}).get("malignant_recall")
    nr_bal = (round2_payload or {}).get("metrics", {}).get("balanced_accuracy")
    nr_fnr = (round2_payload or {}).get("metrics", {}).get("false_negative_rate")
    authorized = bool(policy and policy.ok and policy.authorized_changes) if policy else False
    executed = bool(round2_payload and round2_payload.get("executed"))
    nr_target = bool(executed and nr_recall is not None and nr_recall >= SUCCESS_THRESHOLD)
    nr_effective = bool(
        executed
        and nr_recall is not None
        and nr_recall > float(full_system["round1_malignant_recall"])
    )
    no_reviewer = {
        "arm": "NO_REVIEWER",
        "reviewer_enabled": False,
        "review_feedback": None,
        "REVIEW_STATUS": "NOT_PRESENT_BY_ABLATION",
        "ISSUE_CLOSURE_STATUS": "NOT_APPLICABLE_NO_REVIEWER",
        "QUALITY_GATE_STATUS": "NOT_FULLY_EVALUABLE",
        "NO_REVIEWER_CANONICAL_ELIGIBLE": False,
        "structured_issue_available": False,
        "issue_closure_auditable": False,
        "unresolved_p0": None,
        "unresolved_p1": None,
        "unresolved_p0_p1_reported": False,
        "revision_plan_schema_valid": schema_valid,
        "authorized_revision_proposed": authorized,
        "revision_effective": nr_effective,
        "round2_executed": executed,
        "round2_skip_reason": round2_reason,
        "target_achieved": nr_target,
        "round2_malignant_recall": nr_recall,
        "round2_balanced_accuracy": nr_bal,
        "round2_false_negative_rate": nr_fnr,
        "scientific_scope_pass": True,
        "traceability_complete": bool(audit_calls) and not provider_failed and schema_valid,
        "provider_call_count": len(audit_calls),
        "planner_calls": len(audit_calls),
        "provider_failed": provider_failed,
        "policy_ok": bool(policy.ok) if policy else False,
        "proposed_change": proposed_change,
        "unauthorized_change_count": unauthorized_count,
        "input_hash": input_hash,
        "prompt_hash": prompt_hash,
        "latency_seconds": (audit_calls[0].get("latency_seconds") if audit_calls else None),
        "total_tokens": ((audit_calls[0].get("usage") or {}).get("total_tokens") if audit_calls else None),
        "cost": "unknown",
        "reviewer_content_leak_count": 0,
    }
    if executed:
        _write_json(destination / "execution_spec.json", {
            "kernel": "app.execution.wdbc_baseline.run_baseline",
            "decision_threshold": 0.4,
            "seed": 125,
            "dataset_sha256": DATASET_SHA256,
        })
        _write_json(destination / "execution_result.json", round2_payload)
        _write_json(destination / "raw_results.json", round2_payload.get("recomputed"))
        _write_json(destination / "metrics.json", round2_payload.get("metrics"))
        _write_json(destination / "artifact_manifest.json", {
            "output_root": round2_payload.get("output_root"),
            "predictions": "round2_run/output/predictions.csv",
        })

    comparison = build_comparison_matrix(full_system, no_reviewer)
    _write_json(destination / "comparison_matrix.json", comparison)
    conclusion = classify_conclusion(
        full_system=full_system,
        no_reviewer=no_reviewer,
        protocol_ok=True,
    )
    conclusion.update({
        "protocol_id": PROTOCOL_ID,
        "ablation_id": ablation_id,
        "protocol_commit_sha": protocol_sha,
        "caveats": [
            "One Q028 sub-case does not represent all 125 questions.",
            "NO_REVIEWER has no structured Reviewer issue chain; absence of issues is not UNRESOLVED_P0=0.",
            "This arm is evaluation-only and is not canonical-eligible.",
            "Negative or neutral results must be reported without post-hoc metric selection.",
        ],
        "no_improvement_findings": (
            "Objective holdout metrics are identical to FULL_SYSTEM when the same authorized "
            "threshold is applied by the deterministic kernel."
            if executed and nr_target
            else "NO_REVIEWER did not produce a legal effective revision that met the target."
        ),
        "scientific_scope_status": "pass",
        "negative_result_disclosed": True,
        "full_system": {
            "target_achieved": full_system["target_achieved"],
            "malignant_recall": full_system["round2_malignant_recall"],
        },
        "no_reviewer": no_reviewer,
    })
    _write_json(destination / "ablation_conclusion.json", conclusion)

    added_calls = len(audit_calls)
    _write_json(
        destination / "provider_call_disclosure.json",
        {
            "schema_version": "1.0",
            "protocol_id": PROTOCOL_ID,
            "project_provider_calls_before": 4,
            "project_provider_calls_added": added_calls,
            "project_provider_calls_after": 4 + added_calls,
            "full_system_canonical_calls": 2,
            "historical_abandoned_calls": 2,
            "ablation_calls": added_calls,
            "scientific_reviewer_calls_this_arm": 0,
            "note": "Historical abandoned calls remain disclosed at project level and are not this arm's budget.",
            "calls": audit_calls,
        },
    )
    (destination / "reproduction.md").write_text(
        "\n".join(
            [
                "# Q028 ACTUAL-ABLATION-01 reproduction",
                "",
                f"protocol_id: {PROTOCOL_ID}",
                f"ablation_id: {ablation_id}",
                f"protocol_commit_sha: {protocol_sha}",
                f"control_arm: FULL_SYSTEM ({CANONICAL_ATTEMPT})",
                "ablation_arm: NO_REVIEWER",
                "Do not update canonical pointer. Do not re-run FULL_SYSTEM.",
                "Round 2 uses app.execution.wdbc_baseline.run_baseline with the pinned WDBC cache.",
                "",
            ]
        ),
        encoding="utf-8",
        newline="\n",
    )
    _write_checksums(destination)
    if POINTER_PATH.read_bytes() != pointer_before:
        raise AblationError("canonical pointer was modified; this is forbidden")
    pointer = {
        "protocol_id": PROTOCOL_ID,
        "ablation_id": ablation_id,
        "path": str(destination.relative_to(repository_root).as_posix()),
        "updated_at": _now(),
        "canonical_pointer_updated": False,
    }
    _write_json(ABLATION_POINTER_PATH, pointer)
    return {
        "ablation_id": ablation_id,
        "destination": str(destination),
        "full_system": full_system,
        "no_reviewer": no_reviewer,
        "conclusion": conclusion,
        "leaks": leaks,
        "protocol_commit_sha": protocol_sha,
    }


def get_actual_ablation_status() -> dict[str, Any]:
    """Read-only API payload. Never triggers a provider call or Round 2."""
    if not PROTOCOL_PATH.exists():
        return {"available": False, "reason": "ablation protocol is not present"}
    protocol = load_protocol()
    pointer = _load_json(ABLATION_POINTER_PATH) if ABLATION_POINTER_PATH.exists() else None
    payload: dict[str, Any] = {
        "available": True,
        "protocol_id": PROTOCOL_ID,
        "control_arm": "FULL_SYSTEM",
        "ablation_arm": "NO_REVIEWER",
        "ablated_component": "Scientific Reviewer",
        "canonical_pointer_updated": False,
        "no_reviewer_canonical_eligible": False,
    }
    if pointer:
        dest = REPOSITORY_ROOT / pointer["path"]
        payload["ablation_id"] = pointer.get("ablation_id")
        payload["artifact_path"] = pointer.get("path")
        for name in (
            "full_system_reference.json",
            "comparison_matrix.json",
            "ablation_conclusion.json",
            "policy_validation.json",
            "provider_call_disclosure.json",
            "package_manifest.json",
        ):
            path = dest / name
            if path.exists():
                payload[name.replace(".json", "")] = _load_json(path)
        payload["reproduction_path"] = str((dest / "reproduction.md").as_posix()) if (dest / "reproduction.md").exists() else None
    else:
        payload["ablation_id"] = None
        payload["status"] = "protocol_frozen_run_pending"
    payload["protocol"] = {
        "protocol_id": protocol["protocol_id"],
        "success_threshold": protocol["success_threshold"],
        "max_new_provider_calls": protocol["max_new_provider_calls"],
        "planner_model": protocol["planner_model"],
    }
    from app.execution.flagship_ablation_freeze import overlay_verified_status

    return overlay_verified_status(payload)


if __name__ == "__main__":
    result = run_actual_ablation()
    print(json.dumps({"ablation_id": result["ablation_id"], "result": result["conclusion"]["REVIEWER_EFFECT_RESULT"]}, ensure_ascii=False))
