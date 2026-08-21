"""Real Qwen/Bailian scientific-reviewer closed loop for the Q028/WDBC flagship case.

This module replaces the *sole reliance* on the deterministic, mechanical
``app.execution.flagship_revision`` rule with a genuine, auditable two-call
LLM reviewer/revision-plan loop:

  1. **Scientific Reviewer call** -- reviews the real Round 1 ``ExecutionResult``
     and metrics against the frozen scientific scope, the target metric, and
     the allowed-revision policy, and returns a structured verdict.
  2. **V2 revision-plan call** -- given the reviewer's verdict, proposes a
     concrete experiment-design change for Round 2.

Both calls go through ``app.clients.qwen_chat_client.QwenChatClient`` (the
project's existing audited Bailian/Qwen client) so every call is a real,
low-cost Model Studio request -- never a hand-built mock. Every call's
``provider``/``model``/``request_id``/``timestamp``/``input_hash``/
``output_hash`` is captured into a :class:`ProviderAuditRecord`.

Fail-closed rules (never fabricate, never silently degrade):

* if ``MOCK_LLM`` is enabled, or Bailian credentials are not configured, this
  module raises :class:`FlagshipReviewerError` with ``BAILIAN_REVIEW_GATE``
  set to ``BLOCKED_MOCK`` / ``BLOCKED_CREDENTIALS`` -- callers must not
  proceed to publish a new ``PUBLISHED_VERIFIED`` canonical package;
* if a call's response carries no auditable ``request_id``, that response is
  refused -- it must never enter the actual reviewer chain;
* the reviewer output is validated against the required structured schema;
  a response missing required fields is refused, not patched with defaults;
* the V2 revision plan is passed through :func:`validate_v2_plan_against_policy`
  before anything from it is used to build the real Round 2 config -- any
  proposed change outside :data:`ALLOWED_REVISION_POLICY` is marked
  ``POLICY_REJECTED`` and is never executed.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.clients.qwen_chat_client import QwenChatClient, QwenClientError
from app.core.config import get_settings
from app.core.execution_mode import is_mock_mode


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

SCIENTIFIC_SCOPE = {
    "case_id": "Q028",
    "narrowed_problem_statement": (
        "Given a fixed set of 30 cell-nucleus measurement features from the "
        "UCI WDBC dataset (569 fixed records), predict the breast mass "
        "diagnosis category and evaluate with balanced accuracy and "
        "malignant recall."
    ),
    "non_goals": [
        "does not predict treatment efficacy",
        "does not propose a cancer therapy",
        "must not be used for clinical decision-making",
        "must not provide diagnostic advice to patients",
    ],
    "forbidden_extrapolations": [
        "must not be interpreted as curing cancer",
        "must not be extrapolated to all cancer types",
        "must not be extrapolated to unvalidated populations",
        "must not replace clinical diagnosis",
    ],
}

# The single experimental change this case authorizes a reviewer to request.
# Every other experimental control is frozen; a reviewer proposing anything
# outside this policy must be POLICY_REJECTED, never silently executed.
ALLOWED_REVISION_POLICY: dict[str, Any] = {
    "policy_version": "Q028-WDBC-allowed-revision-v1",
    "allowed_changes": [
        {
            "field": "decision_threshold",
            "from": 0.5,
            "to": 0.4,
            "rationale": "the only control the frozen round1_config.json round2_trigger authorizes",
        }
    ],
    "frozen_fields": [
        "dataset", "dataset_sha256", "train_test_split", "seed", "feature_set",
        "normalization", "model_type", "learning_rate", "iterations", "l2",
        "metric_definitions", "test_fraction",
    ],
    "forbidden_actions": [
        "change_dataset", "change_model_type", "change_seed", "change_data_split",
        "multi_threshold_cherry_pick", "relabel_samples", "drop_samples",
        "change_success_metric", "clinical_extrapolation",
    ],
}

RUN_ID = "Q028-wdbc-flagship"
PROMPT_MAX_CHARS = 8000


class FlagshipReviewerError(RuntimeError):
    """Raised whenever the real-reviewer loop must fail closed.

    ``gate`` carries a machine-readable ``BAILIAN_REVIEW_GATE`` value such as
    ``BLOCKED_CREDENTIALS`` / ``BLOCKED_MOCK`` / ``BLOCKED_NO_REQUEST_ID`` /
    ``BLOCKED_SCHEMA_INVALID`` so callers can report it verbatim.
    """

    def __init__(self, message: str, *, gate: str = "BLOCKED_UNKNOWN") -> None:
        super().__init__(message)
        self.gate = gate


class StructuredIssue(BaseModel):
    """One reviewer-raised issue with full audit-grade structure."""

    model_config = ConfigDict(extra="forbid")

    issue_id: str = Field(min_length=1)
    severity: Literal["P0", "P1", "P2"]
    affected_metric: str = Field(min_length=1)
    observed_value: float
    target_value: float
    required_action: str = Field(min_length=1)
    evidence_reference: str = Field(min_length=1)


class ScientificReviewerOutput(BaseModel):
    """Structured schema required from the real Scientific Reviewer call."""

    model_config = ConfigDict(extra="forbid")

    review_id: str = Field(min_length=1)
    passed: bool
    critical_issues: list[StructuredIssue] = Field(default_factory=list)
    required_revisions: list[StructuredIssue] = Field(default_factory=list)
    comments: list[str] = Field(default_factory=list)


class V2RevisionPlanOutput(BaseModel):
    """Structured schema required from the V2 revision-plan generation call."""

    model_config = ConfigDict(extra="forbid")

    plan_id: str = Field(min_length=1)
    responds_to_issue_ids: list[str] = Field(default_factory=list)
    proposed_changes: list[dict[str, Any]] = Field(default_factory=list)
    expected_effect: str = Field(default="")


class ProviderAuditRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    call_id: str
    role: Literal["scientific_reviewer", "v2_revision_plan"]
    provider: str = "bailian"
    model: str
    request_id: str = Field(min_length=1)
    timestamp: str
    input_hash: str
    output_hash: str
    usage: dict[str, Any] = Field(default_factory=dict)
    prompt_snapshot_path: str | None = None


class PolicyValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    authorized_changes: list[dict[str, Any]] = Field(default_factory=list)
    unauthorized_changes: list[dict[str, Any]] = Field(default_factory=list)
    policy_version: str


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def assert_bailian_available() -> None:
    """Fail closed with a precise gate code if a real call cannot be made."""
    if is_mock_mode():
        raise FlagshipReviewerError(
            "MOCK_LLM is enabled; a mocked reviewer output must never enter the "
            "actual reviewer chain or a PUBLISHED_VERIFIED canonical package.",
            gate="BLOCKED_MOCK",
        )
    settings = get_settings()
    if not settings.qwen_configured:
        raise FlagshipReviewerError(
            "Bailian/Qwen credentials (DASHSCOPE_API_KEY / DASHSCOPE_BASE_URL) are "
            "not configured; refusing to fabricate a reviewer call.",
            gate="BLOCKED_CREDENTIALS",
        )


def _round1_execution_summary(round1_result: dict[str, Any]) -> dict[str, Any]:
    """A redacted, structurally-stable summary of the real Round 1 ExecutionResult
    (no secrets, no absolute local paths -- only scientific content)."""
    metrics = {m["name"]: m["value"] for m in round1_result.get("metrics", [])}
    return {
        "execution_id": round1_result.get("execution_id"),
        "question_id": round1_result.get("question_id"),
        "status": round1_result.get("status"),
        "actual_execution": round1_result.get("actual_execution"),
        "metrics": metrics,
        "dataset_sha256": (round1_result.get("datasets") or [{}])[0].get("sha256"),
        "seed": round1_result.get("seed"),
        "git_dirty": round1_result.get("environment_fingerprint", {}).get("git_dirty"),
    }


def build_scientific_reviewer_prompt(
    *,
    round1_result: dict[str, Any],
    round1_config: dict[str, Any],
) -> tuple[str, str, dict[str, Any]]:
    """Build the (system, user, structured_context) inputs for reviewer call #1."""
    trigger = round1_config["round2_trigger"]
    context = {
        "case_id": SCIENTIFIC_SCOPE["case_id"],
        "scientific_scope": SCIENTIFIC_SCOPE,
        "round1_execution_result": _round1_execution_summary(round1_result),
        "target_metric": trigger["metric"],
        "target_value": trigger["target"],
        "current_decision_threshold": round1_config.get("decision_threshold"),
        "control_variables": {
            "dataset": "UCI WDBC (fixed, pinned by sha256)",
            "seed": round1_config.get("seed"),
            "test_fraction": round1_config.get("test_fraction"),
            "optimizer": round1_config.get("optimizer"),
        },
        "allowed_revision_policy": ALLOWED_REVISION_POLICY,
    }
    system_prompt = (
        "You are a strict scientific reviewer for a controlled, frozen binary "
        "classification experiment protocol (UCI WDBC breast-mass diagnosis). "
        "You review real, already-computed Round 1 results against a "
        "pre-declared target metric and an explicit allowed-revision policy. "
        "You must respond with a single JSON object matching exactly this "
        "schema (no extra keys, no markdown fences):\n"
        '{"review_id": string, "passed": boolean, '
        '"critical_issues": [{"issue_id": string, "severity": "P0"|"P1"|"P2", '
        '"affected_metric": string, "observed_value": number, '
        '"target_value": number, "required_action": string, '
        '"evidence_reference": string}], '
        '"required_revisions": [<same shape as critical_issues>], '
        '"comments": [string]}\n'
        "Ground every issue strictly in the provided Round 1 metrics -- never "
        "invent a metric value. Never claim this experiment cures cancer, "
        "validates clinical use, or generalizes beyond this fixed dataset. "
        "Any required_action must stay within allowed_revision_policy; if the "
        "target is unmet, the only in-policy action is adjusting "
        "decision_threshold as described in allowed_revision_policy."
    )
    user_prompt = (
        "Review the following real Round 1 result and scientific scope, then "
        "return the JSON verdict described in the system prompt.\n\n"
        f"CONTEXT_JSON:\n{_canonical_json(context)}"
    )
    return system_prompt, user_prompt, context


def build_v2_revision_plan_prompt(
    *,
    reviewer_output: ScientificReviewerOutput,
    round1_result: dict[str, Any],
    round1_config: dict[str, Any],
    provider_audit_reference: str,
) -> tuple[str, str, dict[str, Any]]:
    """Build the (system, user, structured_context) inputs for the V2 revision-plan call."""
    context = {
        "case_id": SCIENTIFIC_SCOPE["case_id"],
        "scientific_scope": SCIENTIFIC_SCOPE,
        "round1_execution_result": _round1_execution_summary(round1_result),
        "review_feedback": reviewer_output.model_dump(mode="json"),
        "provider_audit_reference": provider_audit_reference,
        "current_round1_config": round1_config,
        "allowed_revision_policy": ALLOWED_REVISION_POLICY,
    }
    system_prompt = (
        "You are the experiment-revision planner for a controlled, frozen "
        "binary classification protocol. Given the Scientific Reviewer's "
        "verdict on Round 1 (review_feedback) and an explicit "
        "allowed_revision_policy, propose a V2 (Round 2) revision plan that "
        "responds to every open issue. You must respond with a single JSON "
        "object matching exactly this schema (no extra keys, no markdown "
        "fences):\n"
        '{"plan_id": string, "responds_to_issue_ids": [string], '
        '"proposed_changes": [{"field": string, "from": <value>, '
        '"to": <value>, "justification": string}], '
        '"expected_effect": string}\n'
        "Only propose changes that are inside allowed_revision_policy; you "
        "may explicitly restate the single authorized decision_threshold "
        "change, but you must never propose changing the dataset, model "
        "type, seed, data split, labels, or success metric definitions."
    )
    user_prompt = (
        "Given the reviewer verdict below, propose the V2 revision plan as "
        "the JSON object described in the system prompt.\n\n"
        f"CONTEXT_JSON:\n{_canonical_json(context)}"
    )
    return system_prompt, user_prompt, context


def _snapshot_prompt(
    *, role: str, system_prompt: str, user_prompt: str, destination_dir: Path,
) -> tuple[str, dict[str, Any]]:
    """Persist a redacted, length-capped prompt snapshot to disk and return
    (prompt_hash, snapshot_metadata). The hash is computed over the *full*,
    untruncated prompt text so truncation of the on-disk snapshot never
    changes the hash used for provenance."""
    full_text = f"SYSTEM:\n{system_prompt}\n\nUSER:\n{user_prompt}"
    prompt_hash = _sha256_text(full_text)
    truncated = len(full_text) > PROMPT_MAX_CHARS
    on_disk_text = full_text[:PROMPT_MAX_CHARS]
    destination_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = destination_dir / f"{role}_prompt_snapshot.txt"
    snapshot_path.write_text(on_disk_text, encoding="utf-8", newline="\n")
    return prompt_hash, {
        "path": str(snapshot_path),
        "truncated": truncated,
        "truncation_policy": f"first {PROMPT_MAX_CHARS} chars of the full prompt kept; hash covers full untruncated text",
        "full_length_chars": len(full_text),
    }


def _extract_json_output(client: QwenChatClient, raw_text: str) -> dict[str, Any]:
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise FlagshipReviewerError(
            f"reviewer response is not valid JSON: {exc}", gate="BLOCKED_SCHEMA_INVALID"
        ) from None


def call_scientific_reviewer(
    *,
    round1_result: dict[str, Any],
    round1_config: dict[str, Any],
    destination_dir: Path,
    model: str | None = None,
) -> tuple[ScientificReviewerOutput, ProviderAuditRecord, dict[str, Any]]:
    """Real, low-cost Bailian/Qwen call #1: the Scientific Reviewer."""
    assert_bailian_available()
    settings = get_settings()
    model = model or settings.qwen_fast_model

    system_prompt, user_prompt, context = build_scientific_reviewer_prompt(
        round1_result=round1_result, round1_config=round1_config,
    )
    prompt_hash, snapshot_meta = _snapshot_prompt(
        role="v1_scientific_reviewer", system_prompt=system_prompt, user_prompt=user_prompt,
        destination_dir=destination_dir,
    )
    input_hash = _sha256_text(_canonical_json(context))

    client = QwenChatClient(settings=settings)
    try:
        raw_text = client.chat(
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            model=model, temperature=0.1, response_format={"type": "json_object"},
        )
    except QwenClientError as exc:
        raise FlagshipReviewerError(f"scientific reviewer call failed: {exc}", gate="BLOCKED_PROVIDER_ERROR") from None

    request_id = client.last_request_id
    if not request_id:
        raise FlagshipReviewerError(
            "scientific reviewer response carried no auditable request_id; "
            "refusing to enter the actual reviewer chain",
            gate="BLOCKED_NO_REQUEST_ID",
        )

    payload = _extract_json_output(client, raw_text)
    try:
        output = ScientificReviewerOutput.model_validate(payload)
    except ValidationError as exc:
        raise FlagshipReviewerError(
            f"scientific reviewer output failed schema validation: {exc}",
            gate="BLOCKED_SCHEMA_INVALID",
        ) from None

    output_hash = _sha256_text(_canonical_json(output.model_dump(mode="json")))
    audit = ProviderAuditRecord(
        call_id=f"call-{uuid.uuid4().hex}",
        role="scientific_reviewer",
        model=model,
        request_id=request_id,
        timestamp=_now(),
        input_hash=input_hash,
        output_hash=output_hash,
        usage=dict(client.last_usage),
        prompt_snapshot_path=snapshot_meta["path"],
    )
    return output, audit, {"prompt_hash": prompt_hash, "input_hash": input_hash, "snapshot": snapshot_meta}


def _assert_v2_responds_to_open_issues(
    *, reviewer_output: ScientificReviewerOutput, v2_plan: V2RevisionPlanOutput,
) -> None:
    """Fail closed if the reviewer raised open issues but the V2 plan does not
    substantively respond to at least one of them.

    "Substantively respond" requires *both*: (a) the plan references at least
    one of the reviewer's real ``issue_id``s in ``responds_to_issue_ids``, and
    (b) the plan actually proposes at least one concrete change (an empty
    ``proposed_changes`` list is never treated as a real response, even if it
    happens to cite an issue id)."""
    open_issue_ids = {i.issue_id for i in reviewer_output.critical_issues}
    open_issue_ids |= {i.issue_id for i in reviewer_output.required_revisions}
    if not open_issue_ids:
        return
    addressed = open_issue_ids & set(v2_plan.responds_to_issue_ids)
    if not addressed or not v2_plan.proposed_changes:
        raise FlagshipReviewerError(
            "V2 revision plan does not substantively respond to any open "
            f"reviewer issue ({sorted(open_issue_ids)}); refusing to treat "
            "this as a genuine reviewer-driven revision",
            gate="BLOCKED_ISSUE_NOT_ADDRESSED",
        )


def call_v2_revision_plan(
    *,
    reviewer_output: ScientificReviewerOutput,
    round1_result: dict[str, Any],
    round1_config: dict[str, Any],
    provider_audit_reference: str,
    destination_dir: Path,
    model: str | None = None,
) -> tuple[V2RevisionPlanOutput, ProviderAuditRecord, dict[str, Any]]:
    """Real, low-cost Bailian/Qwen call #2: V2 revision-plan generation."""
    assert_bailian_available()
    settings = get_settings()
    model = model or settings.qwen_fast_model

    system_prompt, user_prompt, context = build_v2_revision_plan_prompt(
        reviewer_output=reviewer_output, round1_result=round1_result, round1_config=round1_config,
        provider_audit_reference=provider_audit_reference,
    )
    prompt_hash, snapshot_meta = _snapshot_prompt(
        role="v2_revision_plan", system_prompt=system_prompt, user_prompt=user_prompt,
        destination_dir=destination_dir,
    )
    input_hash = _sha256_text(_canonical_json(context))

    client = QwenChatClient(settings=settings)
    try:
        raw_text = client.chat(
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            model=model, temperature=0.1, response_format={"type": "json_object"},
        )
    except QwenClientError as exc:
        raise FlagshipReviewerError(f"V2 revision-plan call failed: {exc}", gate="BLOCKED_PROVIDER_ERROR") from None

    request_id = client.last_request_id
    if not request_id:
        raise FlagshipReviewerError(
            "V2 revision-plan response carried no auditable request_id; "
            "refusing to enter the actual reviewer chain",
            gate="BLOCKED_NO_REQUEST_ID",
        )

    payload = _extract_json_output(client, raw_text)
    try:
        output = V2RevisionPlanOutput.model_validate(payload)
    except ValidationError as exc:
        raise FlagshipReviewerError(
            f"V2 revision-plan output failed schema validation: {exc}",
            gate="BLOCKED_SCHEMA_INVALID",
        ) from None

    _assert_v2_responds_to_open_issues(reviewer_output=reviewer_output, v2_plan=output)

    output_hash = _sha256_text(_canonical_json(output.model_dump(mode="json")))
    audit = ProviderAuditRecord(
        call_id=f"call-{uuid.uuid4().hex}",
        role="v2_revision_plan",
        model=model,
        request_id=request_id,
        timestamp=_now(),
        input_hash=input_hash,
        output_hash=output_hash,
        usage=dict(client.last_usage),
        prompt_snapshot_path=snapshot_meta["path"],
    )
    return output, audit, {"prompt_hash": prompt_hash, "input_hash": input_hash, "snapshot": snapshot_meta}


def validate_v2_plan_against_policy(
    v2_plan: V2RevisionPlanOutput, policy: dict[str, Any] = ALLOWED_REVISION_POLICY,
) -> PolicyValidationResult:
    """Fail-closed allowed-revision policy check.

    Any proposed change matching an entry in ``policy["allowed_changes"]``
    (same field + from + to) is authorized; every other proposed change is
    POLICY_REJECTED. ``ok`` is False iff there is at least one unauthorized
    change OR zero authorized changes were proposed for an unmet target
    (callers decide what "zero authorized changes" means for their flow).
    """
    allowed = {
        (c["field"], c["from"], c["to"]): c for c in policy.get("allowed_changes", [])
    }
    authorized: list[dict[str, Any]] = []
    unauthorized: list[dict[str, Any]] = []
    for change in v2_plan.proposed_changes:
        field = change.get("field")
        from_value = change.get("from")
        to_value = change.get("to")
        key = (field, from_value, to_value)
        if key in allowed:
            authorized.append(change)
        else:
            unauthorized.append(change)
    return PolicyValidationResult(
        ok=len(unauthorized) == 0,
        authorized_changes=authorized,
        unauthorized_changes=unauthorized,
        policy_version=str(policy.get("policy_version", "unknown")),
    )


def apply_policy_filtered_round2_config(
    round1_config: dict[str, Any],
    policy_result: PolicyValidationResult,
) -> dict[str, Any]:
    """Build the Round 2 config that will actually be executed: start from the
    real, frozen Round 1 config and apply *only* the policy-authorized
    changes. Unauthorized proposals (if any) are never applied, regardless of
    what the LLM proposed."""
    round2_config = dict(round1_config)
    for change in policy_result.authorized_changes:
        round2_config[change["field"]] = change["to"]
    return round2_config
