"""Reproduce the T03 Wave C contract-fixture calibration.

This harness deliberately constructs frozen ``ValidationContext`` snapshots.
It does not call the production pipeline, an API, a model, or a network source.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from datetime import datetime, timezone
from importlib import import_module
from pathlib import Path
from time import perf_counter_ns
from typing import Any


HERE = Path(__file__).resolve().parent
REPOSITORY_ROOT = HERE.parents[3]
DEFAULT_MANIFEST = HERE / "calibration_manifest.json"
DEFAULT_RAW_RESULTS = HERE / "calibration_raw_results.json"
DEFAULT_METRICS = HERE / "calibration_metrics.json"
SELECTION_SOURCE = Path("docs/modules/T01/domain_audit_12.json")
SELECTION_SOURCE_BLOB = "7a1beceb523ec0a946c896d4e148de7707c277ef"
QUESTION_IDS = (
    "Q001",
    "Q012",
    "Q018",
    "Q024",
    "Q028",
    "Q035",
    "Q042",
    "Q051",
    "Q063",
    "Q077",
    "Q089",
    "Q102",
)
MUTATIONS = {
    "missing_evidence_cards",
    "missing_agent_trace",
    "fabricated_reference",
    "missing_dataset_target",
    "fabricated_metric",
    "forbidden_model",
    "incomplete_execution_proof",
    "failed_trace",
    "invalid_prompt_hash",
    "duplicate_evidence_id",
    "missing_reference_id",
    "open_revision_issue",
}
FIXED_REPORT_TIME = datetime(2026, 8, 12, 9, 0, tzinfo=timezone.utc)


def _load_runtime() -> tuple[Any, Any, Any]:
    root = str(REPOSITORY_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    contracts = import_module("app.contracts.validation")
    quality = import_module("app.quality")
    validation = import_module("app.validation")
    return (
        contracts.ValidationContext,
        quality.DefaultQualityGateRunner,
        validation.DefaultValidationService,
    )


def _sha256(value: object) -> str:
    wire = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(wire).hexdigest()


def _require_mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _require_string_list(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise ValueError(f"{label} must be a list of non-blank strings")
    return tuple(value)


def load_manifest(path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    """Load and fail closed on a malformed or misleading fixture manifest."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    manifest = dict(_require_mapping(payload, "manifest"))
    if manifest.get("schema_version") != 1:
        raise ValueError("manifest schema_version must be 1")
    if manifest.get("harness_version") != "t03-wave-c-calibration-v1":
        raise ValueError("manifest harness_version is not supported")
    if manifest.get("dataset_mode") != "contract_fixture":
        raise ValueError("calibration must be labelled contract_fixture")
    if manifest.get("production_pipeline_connected") is not False:
        raise ValueError("contract calibration cannot claim a production pipeline")
    if manifest.get("question_text_is_source_booklet_content") is not False:
        raise ValueError("synthetic question text cannot claim booklet provenance")
    if manifest.get("selection_source") != SELECTION_SOURCE.as_posix():
        raise ValueError("selection_source must use the frozen T01 policy table")
    if manifest.get("selection_source_git_blob") != SELECTION_SOURCE_BLOB:
        raise ValueError("selection_source_git_blob is not the frozen base blob")
    if manifest.get("selection_source_not_live_pipeline_traces") is not True:
        raise ValueError("selection source must preserve its not-live limitation")

    selection = json.loads(
        (REPOSITORY_ROOT / SELECTION_SOURCE).read_text(encoding="utf-8")
    )
    if selection.get("not_live_pipeline_traces") is not True:
        raise ValueError("T01 selection source no longer declares not-live traces")
    selection_rows = selection.get("rows")
    if not isinstance(selection_rows, list) or len(selection_rows) != 12:
        raise ValueError("T01 selection source must contain exactly 12 rows")

    question_ids = _require_string_list(
        manifest.get("question_ids"), "question_ids"
    )
    if question_ids != QUESTION_IDS:
        raise ValueError("manifest must contain the frozen 12-question order")

    questions = manifest.get("questions")
    if not isinstance(questions, list) or len(questions) != len(QUESTION_IDS):
        raise ValueError("manifest must define exactly 12 question fixtures")
    observed_ids: list[str] = []
    observed_mutations: list[str] = []
    for index, raw_question in enumerate(questions):
        question = _require_mapping(raw_question, f"questions[{index}]")
        question_id = question.get("question_id")
        if not isinstance(question_id, str):
            raise ValueError(f"questions[{index}].question_id must be a string")
        observed_ids.append(question_id)
        if not isinstance(question.get("question_text"), str) or not str(
            question["question_text"]
        ).strip():
            raise ValueError(f"questions[{index}].question_text is required")
        source_row = _require_mapping(
            selection_rows[index], f"selection.rows[{index}]"
        )
        if (
            source_row.get("question_id") != question_id
            or source_row.get("domain") != question.get("fixture_domain")
            or source_row.get("topic") != question.get("fixture_topic")
        ):
            raise ValueError(
                f"questions[{index}] must match the frozen T01 id/domain/topic"
            )
        negative = _require_mapping(
            question.get("negative_case"),
            f"questions[{index}].negative_case",
        )
        mutation = negative.get("mutation")
        if mutation not in MUTATIONS:
            raise ValueError(f"unsupported calibration mutation: {mutation}")
        observed_mutations.append(str(mutation))
        if negative.get("expected_status") != "blocked":
            raise ValueError("every negative fixture must expect blocked")
        _require_string_list(
            negative.get("expected_finding_codes"),
            f"questions[{index}].negative_case.expected_finding_codes",
        )
        _require_string_list(
            negative.get("expected_blocking_issue_ids"),
            f"questions[{index}].negative_case.expected_blocking_issue_ids",
        )
    if tuple(observed_ids) != QUESTION_IDS:
        raise ValueError("question fixture order does not match question_ids")
    if len(observed_mutations) != len(set(observed_mutations)):
        raise ValueError("each representative question requires a distinct mutation")
    return manifest


def build_contract_fixture_context(question: Mapping[str, Any]) -> Any:
    """Construct one complete, internally consistent synthetic context."""

    ValidationContext, _, _ = _load_runtime()
    question_id = str(question["question_id"])
    question_text = str(question["question_text"])
    run_id = f"wave-c-calibration-{question_id.lower()}"
    version_id = f"{run_id}:v1"
    evidence_id = f"EV-{question_id}-001"
    evidence_card = {
        "id": evidence_id,
        "run_id": run_id,
        "version_id": version_id,
        "question_id": question_id,
        "source_type": "local",
        "title": f"Synthetic calibration evidence for {question_id}",
        "authors": ["T03 contract-fixture harness"],
        "year": 2026,
        "url": None,
        "doi": None,
        "quoted_text": (
            "A preregistered falsification condition separates a testable "
            "claim from an unsupported success statement."
        ),
        "summary": "Synthetic evidence used only to exercise frozen gates.",
        "relevance_score": 0.95,
        "reliability_note": "contract_fixture only; not live scientific evidence",
    }
    payload = {
        "schema_version": 1,
        "validation_id": f"validation-wave-c-{question_id.lower()}-positive",
        "run_id": run_id,
        "version_id": version_id,
        "research_plan": {
            "run_id": run_id,
            "version_id": version_id,
            "question_id": question_id,
            "input_question": question_text,
            "actual_execution": False,
            "references": [deepcopy(evidence_card)],
            "generated_hypotheses": [
                {
                    "hypothesis": (
                        "A preregistered decision rule makes the fixture "
                        "hypothesis falsifiable."
                    ),
                    "supporting_evidence_ids": [evidence_id],
                    "contradicted_by_evidence_ids": [],
                }
            ],
            "datasets": {
                "source": "synthetic calibration source split",
                "target": "synthetic held-out calibration split",
            },
            "experiments": {
                "baselines": ["fixture-baseline-a", "fixture-baseline-b"],
                "metrics": ["error", "coverage", "stability"],
                "falsification_rule": "reject when the preregistered bound fails",
            },
            "reproducibility_checklist": [
                "pin fixture manifest",
                "record context fingerprint",
                "record finding codes",
            ],
            "results": "待执行验证实验；contract fixture 不报告科学结果。",
            "validation_status": "ready_for_validation",
        },
        "evidence_cards": [evidence_card],
        "agent_trace": [
            {
                "event_id": f"trace-{question_id.lower()}-001",
                "run_id": run_id,
                "version_id": version_id,
                "question_id": question_id,
                "step_index": 1,
                "agent_name": "report_writer",
                "model_name": "qwen3.6-plus",
                "status": "completed",
                "prompt_hash": _sha256(
                    {"question_id": question_id, "question": question_text}
                ),
                "mock": True,
                "errors": [],
            }
        ],
        "execution_metadata": {
            "run_id": run_id,
            "version_id": version_id,
            "question_id": question_id,
            "actual_execution": False,
            "mode": "contract_fixture",
            "production_pipeline_connected": False,
            "fixture_manifest": "calibration_manifest.json",
        },
        "question_item": {
            "id": question_id,
            "question": question_text,
            "run_id": run_id,
            "version_id": version_id,
            "domain": str(question.get("fixture_domain") or "synthetic"),
            "source": "contract_fixture",
        },
        "revision_issues": [],
        "human_feedback": None,
        "correlation_id": f"corr-wave-c-{question_id.lower()}",
    }
    return ValidationContext.model_validate(payload)


def build_negative_context(question: Mapping[str, Any], positive: Any) -> Any:
    """Derive one valid contract snapshot that a gate must block."""

    ValidationContext, _, _ = _load_runtime()
    payload = positive.model_dump(mode="json")
    negative = _require_mapping(question["negative_case"], "negative_case")
    mutation = str(negative["mutation"])
    payload["validation_id"] = (
        f"validation-wave-c-{str(question['question_id']).lower()}-{mutation}"
    )

    if mutation == "missing_evidence_cards":
        payload["evidence_cards"] = []
    elif mutation == "missing_agent_trace":
        payload["agent_trace"] = []
    elif mutation == "fabricated_reference":
        payload["research_plan"]["references"][0]["id"] = "EV-FABRICATED"
    elif mutation == "missing_dataset_target":
        payload["research_plan"]["datasets"].pop("target")
    elif mutation == "fabricated_metric":
        payload["research_plan"]["results"] = (
            "待执行验证实验；accuracy=99% was not actually observed."
        )
    elif mutation == "forbidden_model":
        payload["agent_trace"][0]["model_name"] = "gpt-4o"
    elif mutation == "incomplete_execution_proof":
        payload["research_plan"]["actual_execution"] = True
        payload["research_plan"]["results"] = (
            "An execution claim is intentionally missing its proof chain."
        )
        payload["execution_metadata"]["actual_execution"] = True
        payload["execution_metadata"]["mode"] = "actual"
        payload["agent_trace"][0]["mock"] = False
    elif mutation == "failed_trace":
        payload["agent_trace"][0]["status"] = "failed"
        payload["agent_trace"][0]["errors"] = ["synthetic fixture failure"]
    elif mutation == "invalid_prompt_hash":
        payload["agent_trace"][0]["prompt_hash"] = "not-a-sha256"
    elif mutation == "duplicate_evidence_id":
        payload["evidence_cards"].append(deepcopy(payload["evidence_cards"][0]))
    elif mutation == "missing_reference_id":
        payload["research_plan"]["references"][0]["id"] = ""
    elif mutation == "open_revision_issue":
        question_id = str(question["question_id"])
        payload["revision_issues"] = [
            {
                "issue_id": f"issue-{question_id}-open-p1",
                "status": "open",
                "severity": "P1",
                "opened_in_version": 1,
                "closed_in_version": None,
                "resolution_note": None,
            }
        ]
    else:  # load_manifest already rejects this; keep mutation fail-closed.
        raise ValueError(f"unsupported calibration mutation: {mutation}")
    return ValidationContext.model_validate(payload)


def _case_result(
    *,
    case_id: str,
    question_id: str,
    case_kind: str,
    mutation: str | None,
    expected_status: str,
    expected_finding_codes: Sequence[str],
    expected_blocking_issue_ids: Sequence[str],
    context: Any,
    timer_ns: Callable[[], int],
) -> dict[str, Any]:
    _, DefaultQualityGateRunner, DefaultValidationService = _load_runtime()
    validator = DefaultValidationService(
        DefaultQualityGateRunner(),
        clock=lambda: FIXED_REPORT_TIME,
    )
    started = timer_ns()
    report = validator.validate(context)
    elapsed_ns = max(0, timer_ns() - started)
    actual_codes = sorted(
        {
            finding.code
            for gate in report.gate_results
            for finding in gate.findings
        }
    )
    blocking_issue_ids = sorted(
        issue.issue_id for issue in report.revision_issues if issue.is_blocking
    )
    status_matches = report.validation_status == expected_status
    finding_codes_match = set(expected_finding_codes).issubset(actual_codes)
    blocking_issues_match = set(expected_blocking_issue_ids).issubset(
        blocking_issue_ids
    )
    if expected_status == "passed":
        classification = (
            "true_pass" if report.validation_status == "passed" else "false_block"
        )
    else:
        classification = (
            "true_block" if report.validation_status == "blocked" else "false_pass"
        )
    return {
        "case_id": case_id,
        "question_id": question_id,
        "case_kind": case_kind,
        "mutation": mutation,
        "context_sha256": context.fingerprint(),
        "report_id": report.report_id,
        "expected_status": expected_status,
        "actual_status": report.validation_status,
        "classification": classification,
        "expected_finding_codes": sorted(expected_finding_codes),
        "actual_finding_codes": actual_codes,
        "expected_blocking_issue_ids": sorted(expected_blocking_issue_ids),
        "actual_blocking_issue_ids": blocking_issue_ids,
        "expectations_met": (
            status_matches and finding_codes_match and blocking_issues_match
        ),
        "gate_count": len(report.gate_results),
        "passed_gate_count": sum(gate.passed for gate in report.gate_results),
        "recommended_plan_status": report.recommended_plan_status,
        "duration_ms": round(elapsed_ns / 1_000_000, 6),
    }


def _semantic_digest(cases: Sequence[Mapping[str, Any]]) -> str:
    volatile = {"duration_ms"}
    normalized = [
        {key: value for key, value in case.items() if key not in volatile}
        for case in cases
    ]
    return _sha256(normalized)


def without_observed_timings(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Remove only local wall-clock observations before evidence comparison."""

    normalized = deepcopy(dict(payload))
    normalized.pop("duration_ms", None)
    cases = normalized.get("cases")
    if isinstance(cases, list):
        for case in cases:
            if isinstance(case, dict):
                case.pop("duration_ms", None)
    return normalized


def verify_recorded_artifacts(
    raw_results: Mapping[str, Any],
    metrics: Mapping[str, Any],
    *,
    raw_path: Path = DEFAULT_RAW_RESULTS,
    metrics_path: Path = DEFAULT_METRICS,
) -> None:
    """Fail when checked-in semantic evidence differs from a fresh run."""

    recorded_raw = json.loads(raw_path.read_text(encoding="utf-8"))
    recorded_metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    if without_observed_timings(recorded_raw) != without_observed_timings(
        raw_results
    ):
        raise ValueError("recorded calibration_raw_results.json is stale or altered")
    if without_observed_timings(recorded_metrics) != without_observed_timings(
        metrics
    ):
        raise ValueError("recorded calibration_metrics.json is stale or altered")


def _percentile(values: Sequence[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(len(ordered) * fraction - 1e-12)))
    return ordered[index]


def run_calibration(
    manifest: Mapping[str, Any],
    *,
    timer_ns: Callable[[], int] = perf_counter_ns,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run all 24 cases and return raw observations plus aggregate metrics."""

    cases: list[dict[str, Any]] = []
    for raw_question in manifest["questions"]:
        question = _require_mapping(raw_question, "question")
        question_id = str(question["question_id"])
        positive = build_contract_fixture_context(question)
        cases.append(
            _case_result(
                case_id=f"{question_id}-positive",
                question_id=question_id,
                case_kind="positive",
                mutation=None,
                expected_status="passed",
                expected_finding_codes=(),
                expected_blocking_issue_ids=(),
                context=positive,
                timer_ns=timer_ns,
            )
        )
        negative = _require_mapping(question["negative_case"], "negative_case")
        cases.append(
            _case_result(
                case_id=f"{question_id}-negative-{negative['mutation']}",
                question_id=question_id,
                case_kind="negative",
                mutation=str(negative["mutation"]),
                expected_status=str(negative["expected_status"]),
                expected_finding_codes=tuple(negative["expected_finding_codes"]),
                expected_blocking_issue_ids=tuple(
                    negative["expected_blocking_issue_ids"]
                ),
                context=build_negative_context(question, positive),
                timer_ns=timer_ns,
            )
        )

    durations = [float(case["duration_ms"]) for case in cases]
    positive_cases = [case for case in cases if case["case_kind"] == "positive"]
    negative_cases = [case for case in cases if case["case_kind"] == "negative"]
    false_blocks = [
        case for case in cases if case["classification"] == "false_block"
    ]
    false_passes = [
        case for case in cases if case["classification"] == "false_pass"
    ]
    finding_counts = Counter(
        code for case in cases for code in case["actual_finding_codes"]
    )
    semantic_digest = _semantic_digest(cases)
    raw_results = {
        "schema_version": 1,
        "harness_version": manifest["harness_version"],
        "dataset_mode": "contract_fixture",
        "production_pipeline_connected": False,
        "duration_unit": "milliseconds",
        "question_ids": list(QUESTION_IDS),
        "semantic_digest_sha256": semantic_digest,
        "cases": cases,
    }
    metrics = {
        "schema_version": 1,
        "harness_version": manifest["harness_version"],
        "dataset_mode": "contract_fixture",
        "production_pipeline_connected": False,
        "question_count": len(QUESTION_IDS),
        "case_count": len(cases),
        "positive_case_count": len(positive_cases),
        "negative_case_count": len(negative_cases),
        "expected_pass_count": sum(
            case["expected_status"] == "passed" for case in cases
        ),
        "expected_block_count": sum(
            case["expected_status"] == "blocked" for case in cases
        ),
        "actual_pass_count": sum(
            case["actual_status"] == "passed" for case in cases
        ),
        "actual_block_count": sum(
            case["actual_status"] == "blocked" for case in cases
        ),
        "false_block_count": len(false_blocks),
        "false_block_rate": (
            len(false_blocks) / len(positive_cases) if positive_cases else 0.0
        ),
        "false_pass_count": len(false_passes),
        "false_pass_rate": (
            len(false_passes) / len(negative_cases) if negative_cases else 0.0
        ),
        "expectation_mismatch_count": sum(
            not case["expectations_met"] for case in cases
        ),
        "finding_counts": dict(sorted(finding_counts.items())),
        "duration_ms": {
            "total": round(sum(durations), 6),
            "mean": round(sum(durations) / len(durations), 6),
            "p95": round(_percentile(durations, 0.95), 6),
            "maximum": round(max(durations, default=0.0), 6),
        },
        "semantic_digest_sha256": semantic_digest,
        "limitations": [
            "contract fixtures only",
            "no live pipeline or production API",
            "no model or network invocation",
            "timings are local process observations and are not service SLOs",
        ],
    }
    return raw_results, metrics


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Path to the frozen calibration manifest.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help=(
            "Optional directory for calibration_raw_results.json and "
            "calibration_metrics.json."
        ),
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Run without writing artifacts and fail on any mismatch.",
    )
    args = parser.parse_args(argv)
    if args.verify_only and args.output_dir is not None:
        parser.error("--verify-only and --output-dir are mutually exclusive")

    manifest = load_manifest(args.manifest)
    raw_results, metrics = run_calibration(manifest)
    if args.verify_only:
        try:
            verify_recorded_artifacts(raw_results, metrics)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
    if args.output_dir is not None:
        _write_json(args.output_dir / "calibration_raw_results.json", raw_results)
        _write_json(args.output_dir / "calibration_metrics.json", metrics)
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return 1 if metrics["expectation_mismatch_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
