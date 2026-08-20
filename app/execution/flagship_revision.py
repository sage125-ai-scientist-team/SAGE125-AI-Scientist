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
    ):
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
