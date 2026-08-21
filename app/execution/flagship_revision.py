"""Deterministic reviewer-feedback / revision bridge for the Q028/WDBC flagship case.

The Q028/WDBC two-round scientific closed loop (``app.execution.run_round1`` /
``app.execution.run_round2``) is a controlled, deterministic experiment: Round 2
changes exactly one control (``decision_threshold``) in response to a frozen,
pre-declared rule already recorded in ``experiments/flagship/round1_config.json``
(``round2_trigger``). There is no LLM call in this loop, so this module builds
the project's standard reviewer/revision contracts (``app.contracts.revision``)
*mechanically* from that frozen rule and the real, already-computed Round 1 and
Round 2 metrics.

Nothing here is invented: every ``ReviewFeedback`` sentence, every
``IssueClosure``, and every prompt fingerprint is derived from real files
already committed under ``docs/modules/T05`` and ``experiments/flagship``. If a
required input is missing or the two rounds are not a genuine iteration (same
config fingerprint), this module fails closed with ``FlagshipRevisionError``
instead of guessing.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.contracts.revision import (
    IssueClosure,
    PlanVersion,
    ReviewFeedback,
    RevisionContext,
    issues_from_review_feedback,
)
from app.execution import flagship_reviewer as freviewer


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ROUND1_CONFIG_PATH = REPOSITORY_ROOT / "experiments" / "flagship" / "round1_config.json"
ROUND2_CONFIG_PATH = REPOSITORY_ROOT / "experiments" / "flagship" / "round2_config.json"
ROUND1_PACKAGE_PATH = REPOSITORY_ROOT / "docs" / "modules" / "T05" / "round1"
ROUND2_PACKAGE_PATH = REPOSITORY_ROOT / "docs" / "modules" / "T05" / "round2"

RUN_ID = "Q028-wdbc-flagship"
SCIENTIFIC_LIMITATION_NOTICE = (
    "This case is a controlled binary-classification exercise used to "
    "demonstrate the AI Scientist plan-execute-review-revise workflow. It "
    "does not prove a cure for cancer, does not constitute clinical "
    "validation or medical advice, cannot be extrapolated to all cancers, "
    "and does not replace domain experts or real clinical research."
)


class FlagshipRevisionError(RuntimeError):
    """Required real evidence for the reviewer/revision bridge is missing or invalid."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise FlagshipRevisionError(f"cannot load required evidence: {path}") from None


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str
    )


def config_fingerprint(config: dict[str, Any]) -> str:
    """Stable sha256 fingerprint of a frozen scientific config (the ``prompt hash``
    equivalent for this non-LLM, deterministic experiment track)."""
    return hashlib.sha256(_canonical_json(config).encode("utf-8")).hexdigest()


def build_round1_review_feedback(
    round1_config: dict[str, Any], round1_metrics: dict[str, float]
) -> ReviewFeedback:
    """Derive Round 1 reviewer feedback purely from the frozen trigger rule."""
    trigger = round1_config.get("round2_trigger")
    if not isinstance(trigger, dict):
        raise FlagshipRevisionError("round1_config.json is missing round2_trigger")
    metric_name = trigger["metric"]
    target = trigger["target"]
    step = trigger["threshold_step"]
    try:
        observed = float(round1_metrics[metric_name])
    except (KeyError, TypeError, ValueError):
        raise FlagshipRevisionError(f"round1 metrics missing required '{metric_name}'") from None

    if observed < target:
        return ReviewFeedback(
            passed=False,
            reviewer_comments=[
                f"Round 1 {metric_name}={observed:.6f} is below the "
                f"predeclared target {target}."
            ],
            critical_issues=[],
            required_revisions=[
                f"Decrease decision_threshold by {step} to raise {metric_name}, "
                "per the frozen round2_trigger rule in "
                "experiments/flagship/round1_config.json."
            ],
            risk_level="medium",
            evidence_grounding_score=1.0,
            falsifiability_score=1.0,
            reproducibility_score=1.0,
            reference_reliability_score=1.0,
        )
    return ReviewFeedback(
        passed=True,
        reviewer_comments=[
            f"Round 1 {metric_name}={observed:.6f} met the predeclared target {target}."
        ],
        risk_level="low",
        evidence_grounding_score=1.0,
        falsifiability_score=1.0,
        reproducibility_score=1.0,
        reference_reliability_score=1.0,
    )


def build_round2_review_feedback(
    round1_config: dict[str, Any], round2_metrics: dict[str, float]
) -> ReviewFeedback:
    """Derive Round 2 reviewer feedback from the same frozen target."""
    trigger = round1_config.get("round2_trigger")
    if not isinstance(trigger, dict):
        raise FlagshipRevisionError("round1_config.json is missing round2_trigger")
    metric_name = trigger["metric"]
    target = trigger["target"]
    try:
        observed = float(round2_metrics[metric_name])
    except (KeyError, TypeError, ValueError):
        raise FlagshipRevisionError(f"round2 metrics missing required '{metric_name}'") from None

    if observed >= target:
        return ReviewFeedback(
            passed=True,
            reviewer_comments=[
                f"Round 2 {metric_name}={observed:.6f} meets or exceeds target "
                f"{target} after the reviewed decision_threshold change."
            ],
            risk_level="low",
            evidence_grounding_score=1.0,
            falsifiability_score=1.0,
            reproducibility_score=1.0,
            reference_reliability_score=1.0,
        )
    return ReviewFeedback(
        passed=False,
        critical_issues=[
            f"Round 2 {metric_name}={observed:.6f} is still below target {target} "
            "after the only control change authorized by the frozen protocol."
        ],
        required_revisions=[],
        risk_level="high",
        evidence_grounding_score=1.0,
        falsifiability_score=1.0,
        reproducibility_score=1.0,
        reference_reliability_score=1.0,
    )


def build_issue_closure(
    round1_feedback: ReviewFeedback, round2_feedback: ReviewFeedback
) -> list[IssueClosure]:
    """Open the Round 1 issue(s) and close them only if Round 2 truly resolved them."""
    issues = issues_from_review_feedback(round1_feedback, opened_in_version=1)
    if not issues:
        return issues
    if round2_feedback.passed and not round2_feedback.critical_issues:
        return [
            issue.model_copy(
                update={
                    "status": "resolved",
                    "closed_in_version": 2,
                    "resolution_note": (
                        "Round 2 changed decision_threshold to the value frozen in "
                        "experiments/flagship/round2_config.json; the observed "
                        "metric recomputed from real Round 2 raw predictions now "
                        "meets the predeclared target."
                    ),
                }
            )
            for issue in issues
        ]
    return issues


def build_plan_versions(
    round1_config: dict[str, Any],
    round2_config: dict[str, Any],
    round1_feedback: ReviewFeedback,
    issue_closures: list[IssueClosure],
) -> list[PlanVersion]:
    """Build the V1/V2 plan lineage with real, non-identical config fingerprints."""
    v1_fingerprint = config_fingerprint(round1_config)
    v2_fingerprint = config_fingerprint(round2_config)
    if v1_fingerprint == v2_fingerprint:
        raise FlagshipRevisionError(
            "round1/round2 config fingerprints are identical; this would not be "
            "a true iteration and must not be published"
        )
    v1 = PlanVersion.create(
        run_id=RUN_ID,
        version_number=1,
        revision_iteration=1,
        experiment_design=round1_config,
        prompt_fingerprints={"experiment_design_config": v1_fingerprint},
    )
    v2 = PlanVersion.create(
        run_id=RUN_ID,
        version_number=2,
        revision_iteration=2,
        parent_version_id=v1.version_id,
        experiment_design=round2_config,
        review_feedback=round1_feedback,
        issue_closures=issue_closures,
        prompt_fingerprints={"experiment_design_config": v2_fingerprint},
    )
    return [v1, v2]


def build_revision_context(
    round1_feedback: ReviewFeedback, issue_closures: list[IssueClosure]
) -> RevisionContext:
    """The authoritative input that drove the V1 -> V2 revision."""
    return RevisionContext(
        run_id=RUN_ID,
        revision_iteration=2,
        review_feedback=round1_feedback,
        issue_closures=issue_closures,
    )


def build_structured_diff(
    round1_config: dict[str, Any],
    round2_config: dict[str, Any],
    control_invariants: dict[str, Any],
) -> dict[str, Any]:
    """A structured, machine-checkable diff between the V1 and V2 configs."""
    changed: list[dict[str, Any]] = []
    unchanged: list[str] = []
    for field in ("seed", "test_fraction"):
        if round1_config.get(field) == round2_config.get(field):
            unchanged.append(field)
        else:
            changed.append(
                {"field": field, "from": round1_config.get(field), "to": round2_config.get(field)}
            )
    if round1_config.get("optimizer") == round2_config.get("optimizer"):
        unchanged.append("optimizer")
    else:
        changed.append(
            {
                "field": "optimizer",
                "from": round1_config.get("optimizer"),
                "to": round2_config.get("optimizer"),
            }
        )
    control_change = round2_config.get("control_change") or {}
    if control_change.get("field") == "decision_threshold":
        changed.append(
            {
                "field": "decision_threshold",
                "from": control_change.get("from"),
                "to": control_change.get("to"),
            }
        )
    return {
        "schema_version": "1.0",
        "run_id": RUN_ID,
        "v1_config_fingerprint": config_fingerprint(round1_config),
        "v2_config_fingerprint": config_fingerprint(round2_config),
        "changed_fields": changed,
        "unchanged_fields": unchanged,
        "control_invariants": control_invariants,
        "substantive_diff": len(changed) > 0,
    }


def build_stop_reason(
    round1_config: dict[str, Any],
    round2_metrics: dict[str, float],
    issue_closures: list[IssueClosure],
) -> dict[str, Any]:
    """Decide, from real numbers only, whether the closed loop may stop here."""
    trigger = round1_config.get("round2_trigger")
    if not isinstance(trigger, dict):
        raise FlagshipRevisionError("round1_config.json is missing round2_trigger")
    metric_name = trigger["metric"]
    target = trigger["target"]
    try:
        observed = float(round2_metrics[metric_name])
    except (KeyError, TypeError, ValueError):
        raise FlagshipRevisionError(f"round2 metrics missing required '{metric_name}'") from None

    unresolved_p0 = sum(
        1 for issue in issue_closures if issue.category == "critical_issue" and issue.status != "resolved"
    )
    unresolved_p1 = sum(
        1 for issue in issue_closures if issue.category == "required_revision" and issue.status != "resolved"
    )
    if observed >= target and unresolved_p0 == 0 and unresolved_p1 == 0:
        reason = "target_achieved"
        rationale = (
            f"Round 2 {metric_name}={observed:.6f} meets the predeclared target "
            f"{target}; the single authorized control change (decision_threshold) "
            "resolved the only open required_revision; no further iteration is "
            "authorized under the frozen Q028/WDBC protocol."
        )
    else:
        reason = "unresolved_after_authorized_change"
        rationale = (
            f"Round 2 {metric_name}={observed:.6f} still misses target {target} "
            "after the only control change authorized by the frozen protocol; "
            "further changes require a new frozen review decision and are out "
            "of scope for this closure."
        )
    return {
        "schema_version": "1.0",
        "run_id": RUN_ID,
        "stop_reason": reason,
        "unresolved_p0": unresolved_p0,
        "unresolved_p1": unresolved_p1,
        "target_metric": metric_name,
        "target_value": target,
        "observed_value": observed,
        "rationale": rationale,
        "scientific_limitation": SCIENTIFIC_LIMITATION_NOTICE,
    }


def build_flagship_revision_bundle(
    *,
    round1_config_path: Path = ROUND1_CONFIG_PATH,
    round2_config_path: Path = ROUND2_CONFIG_PATH,
    round1_metrics: dict[str, float],
    round2_metrics: dict[str, float],
    control_invariants: dict[str, Any],
) -> dict[str, Any]:
    """Build the full reviewer/revision/diff/closure/stop-reason bundle.

    All inputs are real, already-computed values; this function performs no
    execution and makes no network or model calls.
    """
    round1_config = _load_json(Path(round1_config_path))
    round2_config = _load_json(Path(round2_config_path))

    round1_feedback = build_round1_review_feedback(round1_config, round1_metrics)
    round2_feedback = build_round2_review_feedback(round1_config, round2_metrics)
    issue_closures = build_issue_closure(round1_feedback, round2_feedback)
    plan_versions = build_plan_versions(round1_config, round2_config, round1_feedback, issue_closures)
    revision_context = build_revision_context(round1_feedback, issue_closures)
    structured_diff = build_structured_diff(round1_config, round2_config, control_invariants)
    stop_reason = build_stop_reason(round1_config, round2_metrics, issue_closures)

    return {
        "reviewer_feedback": {
            "schema_version": "1.0",
            "run_id": RUN_ID,
            "round1_review": round1_feedback.model_dump(mode="json"),
            "round2_review": round2_feedback.model_dump(mode="json"),
        },
        "revision_context": {
            "schema_version": "1.0",
            **revision_context.model_dump(mode="json"),
        },
        "plan_versions": {
            "schema_version": "1.0",
            "run_id": RUN_ID,
            "versions": [version.model_dump(mode="json") for version in plan_versions],
        },
        "issue_closure": {
            "schema_version": "1.0",
            "run_id": RUN_ID,
            "issues": [issue.model_dump(mode="json") for issue in issue_closures],
            "unresolved_p0": sum(
                1 for issue in issue_closures if issue.category == "critical_issue" and issue.status != "resolved"
            ),
            "unresolved_p1": sum(
                1 for issue in issue_closures if issue.category == "required_revision" and issue.status != "resolved"
            ),
        },
        "structured_diff": structured_diff,
        "stop_reason": stop_reason,
    }


def _structured_issue_to_text(issue: "freviewer.StructuredIssue") -> str:
    return (
        f"[{issue.issue_id}|{issue.severity}] {issue.required_action} "
        f"(metric={issue.affected_metric} observed={issue.observed_value:.6f} "
        f"target={issue.target_value}; evidence={issue.evidence_reference})"
    )


def review_feedback_from_reviewer_output(
    output: "freviewer.ScientificReviewerOutput",
) -> ReviewFeedback:
    """Project the real, structured Scientific Reviewer output onto the
    project's ``ReviewFeedback`` contract (which stores issues as free-text
    strings). Every structured field is preserved verbatim inside the text so
    no information is lost; the original structured object is also kept
    alongside in the on-disk bundle (``structured_round1_review``)."""
    critical = [_structured_issue_to_text(i) for i in output.critical_issues]
    required = [_structured_issue_to_text(i) for i in output.required_revisions]
    if output.critical_issues:
        risk: str = "high"
    elif output.required_revisions:
        risk = "medium"
    else:
        risk = "low"
    return ReviewFeedback(
        passed=output.passed,
        reviewer_comments=list(output.comments),
        critical_issues=critical,
        required_revisions=required,
        risk_level=risk,  # type: ignore[arg-type]
        evidence_grounding_score=1.0,
        falsifiability_score=1.0,
        reproducibility_score=1.0,
        reference_reliability_score=1.0,
    )


def prepare_real_reviewer_round2_config(
    *,
    round1_result: dict[str, Any],
    round1_config: dict[str, Any],
    destination_dir: Path,
) -> dict[str, Any]:
    """Run the two real, audited Bailian/Qwen calls (Scientific Reviewer, then
    V2 revision-plan generation) and derive the policy-filtered Round 2
    config that will actually be executed.

    Must be called *before* Round 2 executes -- its output (``round2_config``)
    is exactly the config Round 2 must run with. Raises
    ``app.execution.flagship_reviewer.FlagshipReviewerError`` (fail closed)
    if credentials are unavailable, mock mode is enabled, or either call
    fails schema/audit validation.
    """
    reviewer_output, reviewer_audit, v1_hashes = freviewer.call_scientific_reviewer(
        round1_result=round1_result, round1_config=round1_config, destination_dir=destination_dir,
    )
    v2_output, v2_audit, v2_hashes = freviewer.call_v2_revision_plan(
        reviewer_output=reviewer_output,
        round1_result=round1_result,
        round1_config=round1_config,
        provider_audit_reference=reviewer_audit.call_id,
        destination_dir=destination_dir,
    )
    policy_result = freviewer.validate_v2_plan_against_policy(v2_output)
    round2_config = freviewer.apply_policy_filtered_round2_config(round1_config, policy_result)
    review_feedback = review_feedback_from_reviewer_output(reviewer_output)
    return {
        "reviewer_output": reviewer_output,
        "v2_output": v2_output,
        "policy_result": policy_result,
        "round2_config": round2_config,
        "reviewer_audit": reviewer_audit,
        "v2_audit": v2_audit,
        "v1_hashes": v1_hashes,
        "v2_hashes": v2_hashes,
        "review_feedback": review_feedback,
    }


def build_real_reviewer_driven_bundle(
    *,
    preparation: dict[str, Any],
    round1_config: dict[str, Any],
    round2_metrics: dict[str, float],
    control_invariants: dict[str, Any],
    round1_version_id: str,
    round1_execution_result_reference: dict[str, Any],
) -> dict[str, Any]:
    """Build the full reviewer/revision/diff/closure/stop-reason bundle from a
    REAL, audited reviewer + V2 revision-plan pair (closes GAP-02).

    Must be called *after* Round 2 has actually executed (real
    ``round2_metrics`` are required to determine issue closure and the stop
    decision -- this function never fabricates them).
    """
    round1_feedback: ReviewFeedback = preparation["review_feedback"]
    reviewer_output: freviewer.ScientificReviewerOutput = preparation["reviewer_output"]
    v2_output: freviewer.V2RevisionPlanOutput = preparation["v2_output"]
    policy_result: freviewer.PolicyValidationResult = preparation["policy_result"]
    round2_config: dict[str, Any] = preparation["round2_config"]
    reviewer_audit: freviewer.ProviderAuditRecord = preparation["reviewer_audit"]
    v2_audit: freviewer.ProviderAuditRecord = preparation["v2_audit"]
    v1_hashes: dict[str, Any] = preparation["v1_hashes"]
    v2_hashes: dict[str, Any] = preparation["v2_hashes"]

    if not round1_version_id or not isinstance(round1_execution_result_reference, dict) or not round1_execution_result_reference.get("execution_id"):
        raise FlagshipRevisionError(
            "round1_version_id / round1_execution_result_reference (with a real "
            "execution_id) must be provided -- the Round 1 ExecutionResult must "
            "be genuinely injected into RevisionContext, not fabricated or omitted"
        )
    if reviewer_audit.role != "scientific_reviewer" or v2_audit.role != "v2_revision_plan":
        raise FlagshipRevisionError(
            "provider audit records are inconsistent with their declared roles; "
            "refusing to attribute this revision to real reviewer calls"
        )

    round2_feedback = build_round2_review_feedback(round1_config, round2_metrics)
    issue_closures = build_issue_closure(round1_feedback, round2_feedback)

    v1_fingerprint = config_fingerprint(round1_config)
    v2_fingerprint = config_fingerprint(round2_config)
    if v1_fingerprint == v2_fingerprint:
        raise FlagshipRevisionError(
            "round1/round2 config fingerprints are identical; this would not be "
            "a true iteration and must not be published"
        )
    if v1_hashes["prompt_hash"] == v2_hashes["prompt_hash"] or v1_hashes["input_hash"] == v2_hashes["input_hash"]:
        raise FlagshipRevisionError(
            "V1/V2 reviewer prompt or input hash did not change; this would not "
            "be a genuine reviewer-driven iteration and must not be published"
        )

    v1 = PlanVersion.create(
        run_id=RUN_ID,
        version_number=1,
        revision_iteration=1,
        experiment_design=round1_config,
        prompt_fingerprints={
            "experiment_design_config": v1_fingerprint,
            "reviewer_prompt_hash": v1_hashes["prompt_hash"],
            "reviewer_input_hash": v1_hashes["input_hash"],
        },
    )
    v2 = PlanVersion.create(
        run_id=RUN_ID,
        version_number=2,
        revision_iteration=2,
        parent_version_id=v1.version_id,
        experiment_design=round2_config,
        review_feedback=round1_feedback,
        issue_closures=issue_closures,
        prompt_fingerprints={
            "experiment_design_config": v2_fingerprint,
            "v2_plan_prompt_hash": v2_hashes["prompt_hash"],
            "v2_plan_input_hash": v2_hashes["input_hash"],
        },
    )
    plan_versions = [v1, v2]

    revision_context = RevisionContext(
        run_id=RUN_ID,
        revision_iteration=2,
        review_feedback=round1_feedback,
        issue_closures=issue_closures,
    )

    structured_diff = build_structured_diff(round1_config, round2_config, control_invariants)
    structured_diff["policy_authorized_changes"] = policy_result.authorized_changes
    structured_diff["policy_rejected_changes"] = policy_result.unauthorized_changes
    structured_diff["policy_version"] = policy_result.policy_version

    stop_reason = build_stop_reason(round1_config, round2_metrics, issue_closures)

    provider_audit = {
        "schema_version": "1.0",
        "run_id": RUN_ID,
        "calls": [reviewer_audit.model_dump(mode="json"), v2_audit.model_dump(mode="json")],
    }

    return {
        "reviewer_feedback": {
            "schema_version": "1.0",
            "run_id": RUN_ID,
            "round1_review": round1_feedback.model_dump(mode="json"),
            "round2_review": round2_feedback.model_dump(mode="json"),
            "structured_round1_review": reviewer_output.model_dump(mode="json"),
            "structured_v2_plan": v2_output.model_dump(mode="json"),
            "reviewer_driven": True,
            "provider_audit_reference": [reviewer_audit.call_id, v2_audit.call_id],
        },
        "revision_context": {
            "schema_version": "1.0",
            **revision_context.model_dump(mode="json"),
            "round1_version_id": round1_version_id,
            "round1_execution_result_reference": round1_execution_result_reference,
            "scientific_scope": freviewer.SCIENTIFIC_SCOPE,
            "allowed_revision_policy": freviewer.ALLOWED_REVISION_POLICY,
            "provider_audit_references": [reviewer_audit.call_id, v2_audit.call_id],
            "reviewer_issues_injected": True,
            "execution_result_injected": True,
        },
        "plan_versions": {
            "schema_version": "1.0",
            "run_id": RUN_ID,
            "versions": [version.model_dump(mode="json") for version in plan_versions],
        },
        "issue_closure": {
            "schema_version": "1.0",
            "run_id": RUN_ID,
            "issues": [issue.model_dump(mode="json") for issue in issue_closures],
            "unresolved_p0": sum(
                1 for issue in issue_closures if issue.category == "critical_issue" and issue.status != "resolved"
            ),
            "unresolved_p1": sum(
                1 for issue in issue_closures if issue.category == "required_revision" and issue.status != "resolved"
            ),
        },
        "structured_diff": structured_diff,
        "stop_reason": stop_reason,
        "provider_audit": provider_audit,
        "policy_validation": {
            "schema_version": "1.0",
            "ok": policy_result.ok,
            "authorized_changes": policy_result.authorized_changes,
            "unauthorized_changes": policy_result.unauthorized_changes,
            "policy_version": policy_result.policy_version,
        },
    }


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, allow_nan=False, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_flagship_revision_bundle(
    bundle: dict[str, Any], destination_dir: Path
) -> dict[str, Path]:
    """Persist the bundle as individual JSON artifacts under ``destination_dir``."""
    destination_dir = Path(destination_dir)
    written: dict[str, Path] = {}
    for name in (
        "reviewer_feedback",
        "revision_context",
        "plan_versions",
        "issue_closure",
        "structured_diff",
        "stop_reason",
        "provider_audit",
        "policy_validation",
    ):
        if name not in bundle:
            continue
        path = destination_dir / f"{name}.json"
        _write_json(path, bundle[name])
        written[name] = path
    return written


def load_round1_metrics(round1_package: Path = ROUND1_PACKAGE_PATH) -> dict[str, float]:
    summary = _load_json(Path(round1_package) / "artifacts" / "run-summary.json")
    metrics = summary.get("metrics")
    if not isinstance(metrics, dict):
        raise FlagshipRevisionError("round1 run-summary.json is missing metrics")
    return metrics


def load_round2_metrics(round2_package: Path = ROUND2_PACKAGE_PATH) -> dict[str, float]:
    summary = _load_json(Path(round2_package) / "artifacts" / "run-summary.json")
    metrics = summary.get("metrics")
    if not isinstance(metrics, dict):
        raise FlagshipRevisionError("round2 run-summary.json is missing metrics")
    return metrics


def build_and_write_from_disk(
    *,
    round1_package: Path = ROUND1_PACKAGE_PATH,
    round2_package: Path = ROUND2_PACKAGE_PATH,
    round1_config_path: Path = ROUND1_CONFIG_PATH,
    round2_config_path: Path = ROUND2_CONFIG_PATH,
    destination_dir: Path | None = None,
) -> dict[str, Any]:
    """Convenience entrypoint: read real Round 1/2 evidence from disk, build and
    write the full reviewer/revision/diff/closure/stop-reason bundle.

    Raises ``FlagshipRevisionError`` (fail closed) if Round 2 evidence does not
    yet exist on disk; callers must not fabricate a Round 2 result.
    """
    round2_package = Path(round2_package)
    if not (round2_package / "execution_result.json").exists():
        raise FlagshipRevisionError(
            "Round 2 has not been formally executed; refusing to fabricate "
            "reviewer feedback for a nonexistent revision"
        )
    round1_metrics = load_round1_metrics(round1_package)
    round2_metrics = load_round2_metrics(round2_package)
    control_invariants = _load_json(
        Path(round2_package) / "comparison" / "control-invariants.json"
    )
    bundle = build_flagship_revision_bundle(
        round1_config_path=round1_config_path,
        round2_config_path=round2_config_path,
        round1_metrics=round1_metrics,
        round2_metrics=round2_metrics,
        control_invariants=control_invariants,
    )
    if destination_dir is not None:
        write_flagship_revision_bundle(bundle, Path(destination_dir))
    return bundle
