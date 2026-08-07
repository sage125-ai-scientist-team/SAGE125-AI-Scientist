"""Offline contract tests for the frozen WB5 formal execution entrypoint."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

import app.batch.formal_five_runs as formal_runner
from app.batch.actual_call_audit import ActualCallAudit, CostAccountingMode
from app.batch.completion_gate import CompletionGateResult, evaluate_question_completion
from app.batch.errors import BatchRunnerError
from app.batch.five_run_preflight import load_frozen_run_config
from app.batch.formal_five_runs import (
    AUTHORIZATION_TEXT,
    FROZEN_EXECUTION_ORDER,
    FormalQuestionExecution,
    FormalRunRequest,
    run_formal_five_runs,
    validate_provider_preflight_audit,
)
from app.contracts.validation import GateFinding, GateResult, Severity
from scripts.batch_125.run_five_real_runs import build_parser


REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG = REPO_ROOT / "docs/modules/T07/run_configs/T07-WB5-20260807-v2.json"
AUTHORIZATION_URL = (
    "https://github.com/sage125-ai-scientist-team/"
    "SAGE125-AI-Scientist/pull/31#issuecomment-5212109429"
)
NOW = datetime(2026, 8, 7, 3, 58, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _isolate_runner_contract_from_untracked_authoritative_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep runner unit tests independent from production-only data files.

    Source-file existence, size, hashes, and frozen mapping are exercised in
    ``test_frozen_five_run_config.py`` with temporary synthetic inputs.  This
    module tests orchestration behavior, so it injects the already tracked
    frozen metadata instead of requiring local ``data/**`` material in CI.
    Production defaults remain unchanged.
    """

    config = load_frozen_run_config(CONFIG)
    mapped = {
        item.question_id: {
            "id": item.question_id,
            "question": item.question,
            "domain": item.domain,
        }
        for item in config.questions
    }
    monkeypatch.setattr(
        formal_runner,
        "_validate_frozen_config",
        lambda _path, _repo_root: config,
    )
    monkeypatch.setattr(
        formal_runner,
        "load_and_map_authoritative_questions",
        lambda _config, _repo_root: mapped,
    )


def _audit(**updates) -> ActualCallAudit:
    payload = {
        "provider": "bailian",
        "model": "qwen3.6-flash",
        "route_tier": "fast",
        "request_timestamp": NOW,
        "sanitized_request_id": "req_sha256:" + "a" * 64,
        "static_prompt_version": "sage125-agent-prompts-20260803-v1",
        "static_prompt_hash": "b" * 64,
        "dynamic_prompt_hash": "c" * 64,
        "input_tokens": 17,
        "output_tokens": 2,
        "total_tokens": 19,
        "estimated_cost_usd": None,
        "settled_cost_usd": None,
        "retry_attempt": 1,
        "fallback": False,
        "price_snapshot_version": None,
        "cost_accounting_mode": CostAccountingMode.TOKEN_ONLY,
    }
    payload.update(updates)
    return ActualCallAudit(**payload)


def _write_preflight_audit(root: Path, **updates) -> Path:
    path = root / "provider_preflight" / "llm_call_audit.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_audit(**updates).to_json() + "\n", encoding="utf-8")
    return path


def _request(tmp_path: Path, **updates) -> FormalRunRequest:
    audit = updates.pop("provider_preflight_audit", None)
    if audit is None:
        audit = _write_preflight_audit(tmp_path / "preflight")
    payload = {
        "repo_root": REPO_ROOT,
        "config_path": CONFIG,
        "run_root": tmp_path / "formal-run",
        "authorization_reference": AUTHORIZATION_URL,
        "provider_preflight_audit": audit,
        "question_ids": ("Q001",),
        "execute": True,
        "resume": False,
        "provider_configured": True,
        "mock_environment": False,
    }
    payload.update(updates)
    return FormalRunRequest(**payload)


def _execution(*, actual_execution: bool = True, audits=None, report_pdf=True):
    calls = (_audit(),) if audits is None else tuple(audits)
    return FormalQuestionExecution(
        report_pdf=(b"%PDF-1.7\n% formal fake\n" if report_pdf else None),
        report_markdown="# Formal fake report\n",
        standard_fields={
            "Problem": "Prime-number structure",
            "Rationale": "Auditable mathematical synthesis",
            "Technical Details": "Offline fake executor",
            "Datasets Source": "Authoritative booklet",
            "Datasets Target": "Evidence bundle",
            "Title": "Prime numbers",
            "Abstract": "A test-only formal artifact.",
            "Methods": "Structured evidence synthesis",
            "Experiments": "No fabricated experiment",
            "Results": "Evidence-backed synthesis only",
            "References": "EV-Q001-001",
        },
        research_plan={
            "question_id": "Q001",
            "input_question": "What makes prime numbers so special?",
            "actual_execution": actual_execution,
            "references": [{"id": "EV-Q001-001"}],
        },
        evidence_cards=(
            {
                "id": "EV-Q001-001",
                "title": "Prime-number evidence",
                "source": {"kind": "booklet", "reference": "sjtu-booklet.pdf"},
            },
        ),
        agent_trace=(
            {
                "agent_name": "formal_fake",
                "status": "completed",
                "prompt_hash": "c" * 64,
            },
        ),
        execution_metadata={
            "actual_execution": actual_execution,
            "mode": "actual" if actual_execution else "planned",
        },
        evidence_bundle={"bundle_id": "fake-bundle"},
        claims=(),
        call_audits=calls,
        duration_seconds=0.1,
    )


def _passed_gate(gate_id: str) -> GateResult:
    return GateResult(gate_id=gate_id, passed=True, severity=Severity.P3, score=1.0)


def _failed_gate(gate_id: str, code: str) -> GateResult:
    return GateResult(
        gate_id=gate_id,
        passed=False,
        severity=Severity.P1,
        findings=(
            GateFinding(
                code=code,
                message="blocked for test",
                severity=Severity.P1,
                closure_status="open",
            ),
        ),
        errors=("blocked for test",),
        score=0.0,
    )


def _evaluate(value, *, t01_pass=True, t03_pass=True):
    return evaluate_question_completion(
        value,
        t01_runner=(
            (lambda *_: _passed_gate("t01"))
            if t01_pass
            else (lambda *_: _failed_gate("t01", "T01_BLOCKED"))
        ),
        t03_runner=(
            (lambda *_: (_passed_gate("t03"),))
            if t03_pass
            else (lambda *_: (_failed_gate("t03", "T03_BLOCKED"),))
        ),
    )


def test_authorization_constant_is_exact() -> None:
    assert AUTHORIZATION_TEXT == "FIVE_REAL_RUNS_AUTHORIZED=true"


def test_cli_is_dry_run_by_default_and_accepts_required_contract() -> None:
    args = build_parser().parse_args(
        [
            "--run-root",
            "D:/external-run",
            "--authorization-reference",
            AUTHORIZATION_URL,
            "--provider-preflight-audit",
            "D:/external-audit/llm_call_audit.json",
            "--question-id",
            "Q001",
        ]
    )

    assert args.execute is False
    assert args.resume is False
    assert args.question_id == ["Q001"]


def test_cli_initializes_and_injects_production_executor(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import scripts.batch_125.run_five_real_runs as command

    executor = object()
    captured = {}

    class _Settings:
        qwen_configured = True
        deep_research_configured = True
        llm_provider = "bailian"

    class _Receipt:
        status = "failed"

        @staticmethod
        def to_dict():
            return {"status": "failed"}

    monkeypatch.setattr(command, "get_settings", lambda: _Settings())
    monkeypatch.setattr(
        command,
        "build_formal_provider_executor",
        lambda _settings: executor,
    )

    def fake_run(request, *, executor=None):
        captured["request"] = request
        captured["executor"] = executor
        return _Receipt()

    monkeypatch.setattr(command, "run_formal_five_runs", fake_run)
    code = command.main(
        [
            "--run-root",
            str(tmp_path / "outside"),
            "--authorization-reference",
            AUTHORIZATION_URL,
            "--provider-preflight-audit",
            str(tmp_path / "preflight.json"),
            "--question-id",
            "Q001",
            "--execute",
        ]
    )

    assert code == 2
    assert captured["request"].execute is True
    assert captured["executor"] is executor


@pytest.mark.parametrize("reference", ["", "   "])
def test_blank_authorization_reference_is_rejected(tmp_path: Path, reference: str) -> None:
    with pytest.raises(BatchRunnerError) as captured:
        run_formal_five_runs(_request(tmp_path, authorization_reference=reference))
    assert captured.value.error_code == "FIVE_REAL_RUNS_AUTHORIZATION_MISSING"


def test_provider_preflight_audit_missing_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(BatchRunnerError) as captured:
        run_formal_five_runs(
            _request(
                tmp_path,
                provider_preflight_audit=tmp_path / "missing.json",
            )
        )
    assert captured.value.error_code == "PROVIDER_PREFLIGHT_AUDIT_MISSING"


def test_provider_preflight_audit_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    path = _write_preflight_audit(tmp_path)
    with pytest.raises(BatchRunnerError) as captured:
        validate_provider_preflight_audit(
            path,
            REPO_ROOT,
            expected_sha256="f" * 64,
        )
    assert captured.value.error_code == "PROVIDER_PREFLIGHT_AUDIT_HASH_MISMATCH"


def test_provider_preflight_fallback_is_rejected(tmp_path: Path) -> None:
    path = _write_preflight_audit(tmp_path, fallback=True)
    with pytest.raises(BatchRunnerError) as captured:
        validate_provider_preflight_audit(path, REPO_ROOT)
    assert captured.value.error_code == "FALLBACK_NOT_ALLOWED"


def test_run_root_inside_repository_is_rejected() -> None:
    request = FormalRunRequest(
        repo_root=REPO_ROOT,
        config_path=CONFIG,
        run_root=REPO_ROOT / ".pytest_tmp/formal",
        authorization_reference=AUTHORIZATION_URL,
        provider_preflight_audit=REPO_ROOT / "not-used.json",
        question_ids=("Q001",),
        execute=False,
    )
    with pytest.raises(BatchRunnerError) as captured:
        run_formal_five_runs(request)
    assert captured.value.error_code == "FORMAL_RUN_ROOT_INVALID"


def test_non_frozen_id_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(BatchRunnerError) as captured:
        run_formal_five_runs(_request(tmp_path, question_ids=("Q999",)))
    assert captured.value.error_code == "FROZEN_QUESTION_ID_INVALID"


def test_frozen_question_order_cannot_be_changed(tmp_path: Path) -> None:
    assert FROZEN_EXECUTION_ORDER == ("Q001", "Q028", "Q050", "Q075", "Q107")
    with pytest.raises(BatchRunnerError) as captured:
        run_formal_five_runs(
            _request(tmp_path, question_ids=("Q028", "Q001"))
        )
    assert captured.value.error_code == "FROZEN_QUESTION_ORDER_INVALID"


def test_mock_environment_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(BatchRunnerError) as captured:
        run_formal_five_runs(_request(tmp_path, mock_environment=True))
    assert captured.value.error_code == "FORMAL_MOCK_FORBIDDEN"


def test_incomplete_call_audit_is_fail_closed(tmp_path: Path) -> None:
    receipt = run_formal_five_runs(
        _request(tmp_path),
        executor=lambda _context: _execution(audits=()),
        completion_evaluator=_evaluate,
    )
    assert receipt.status == "failed"
    assert receipt.questions[0].error_codes == ("CALL_AUDIT_INCOMPLETE",)


def test_call_audit_fallback_is_fail_closed(tmp_path: Path) -> None:
    receipt = run_formal_five_runs(
        _request(tmp_path),
        executor=lambda _context: _execution(audits=(_audit(fallback=True),)),
        completion_evaluator=_evaluate,
    )
    assert receipt.questions[0].error_codes == ("FALLBACK_NOT_ALLOWED",)


def test_missing_report_pdf_blocks_completion(tmp_path: Path) -> None:
    receipt = run_formal_five_runs(
        _request(tmp_path),
        executor=lambda _context: _execution(report_pdf=False),
        completion_evaluator=_evaluate,
    )
    assert "REQUIRED_ARTIFACT_MISSING" in receipt.questions[0].error_codes
    assert receipt.progress == "0/5"


def test_actual_execution_false_cannot_complete(tmp_path: Path) -> None:
    receipt = run_formal_five_runs(
        _request(tmp_path),
        executor=lambda _context: _execution(actual_execution=False),
        completion_evaluator=_evaluate,
    )
    assert receipt.status == "gates_pending"
    assert "ACTUAL_CONTEXT_INVALID" in receipt.questions[0].error_codes


@pytest.mark.parametrize(
    ("t01_pass", "t03_pass", "expected"),
    [(False, True, "T01_GATE_FAILED"), (True, False, "T03_GATE_FAILED")],
)
def test_t01_or_t03_failure_cannot_complete(
    tmp_path: Path,
    t01_pass: bool,
    t03_pass: bool,
    expected: str,
) -> None:
    receipt = run_formal_five_runs(
        _request(tmp_path),
        executor=lambda _context: _execution(),
        completion_evaluator=lambda value: _evaluate(
            value,
            t01_pass=t01_pass,
            t03_pass=t03_pass,
        ),
    )
    assert expected in receipt.questions[0].error_codes
    assert not receipt.questions[0].completed


def test_token_limit_stops_question(tmp_path: Path) -> None:
    oversized = _audit(
        input_tokens=200000,
        output_tokens=1,
        total_tokens=200001,
    )
    receipt = run_formal_five_runs(
        _request(tmp_path),
        executor=lambda _context: _execution(audits=(oversized,)),
        completion_evaluator=_evaluate,
    )
    assert receipt.questions[0].error_codes == ("BUDGET_EXHAUSTED",)


def test_q001_failure_prevents_q028_execution(tmp_path: Path) -> None:
    called: list[str] = []

    def failing(context):
        called.append(context.question_id)
        raise BatchRunnerError("Q001_FAILED", "synthetic failure")

    receipt = run_formal_five_runs(
        _request(tmp_path, question_ids=("Q001", "Q028")),
        executor=failing,
        completion_evaluator=_evaluate,
    )
    assert called == ["Q001"]
    assert len(receipt.questions) == 1
    assert receipt.questions[0].error_codes == ("Q001_FAILED",)


def test_call_audit_persist_failure_has_safe_specific_code(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request(tmp_path)
    original_write_text = Path.write_text

    def fail_only_formal_call_audit(path: Path, *args, **kwargs):
        if path.name == "llm_call_audit.json" and path.parent.name == "Q001":
            raise OSError("SENSITIVE_TEST_VALUE")
        return original_write_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_only_formal_call_audit)
    receipt = run_formal_five_runs(
        request,
        executor=lambda _context: _execution(),
        completion_evaluator=_evaluate,
    )

    assert receipt.status == "failed"
    assert receipt.questions[0].error_codes == ("AUDIT_PERSIST_FAILED",)
    checkpoint = (
        Path(receipt.batch_root) / "Q001/checkpoint.json"
    ).read_text(encoding="utf-8")
    assert "SENSITIVE_TEST_VALUE" not in checkpoint


def test_completed_status_only_comes_from_completion_evaluator(tmp_path: Path) -> None:
    pending = CompletionGateResult(
        status="gates_pending",
        completed=False,
        conditions={"forced_pending": False},
        issues=(),
        gate_results=(),
        validation_report=None,
    )
    receipt = run_formal_five_runs(
        _request(tmp_path),
        executor=lambda _context: _execution(),
        completion_evaluator=lambda _value: pending,
    )
    assert receipt.status == "gates_pending"
    assert receipt.progress == "0/5"
    assert not receipt.questions[0].completed


def test_success_writes_authorization_audit_and_no_secret(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "secret-must-never-be-persisted"
    monkeypatch.setenv("DASHSCOPE_API_KEY", secret)
    receipt = run_formal_five_runs(
        _request(tmp_path),
        executor=lambda _context: _execution(),
        completion_evaluator=_evaluate,
    )
    assert receipt.status == "completed"
    assert receipt.progress == "1/5"
    batch_root = Path(receipt.batch_root)
    manifest = json.loads((batch_root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["authorization_reference"] == AUTHORIZATION_URL
    assert manifest["provider_preflight_audit"]["sha256"]
    for path in batch_root.rglob("*"):
        if path.is_file():
            assert secret.encode() not in path.read_bytes()


def test_resume_completed_question_does_not_repeat_executor(tmp_path: Path) -> None:
    request = _request(tmp_path)
    first = run_formal_five_runs(
        request,
        executor=lambda _context: _execution(),
        completion_evaluator=_evaluate,
    )
    assert first.status == "completed"

    calls = 0

    def forbidden(_context):
        nonlocal calls
        calls += 1
        raise AssertionError("completed call was repeated")

    resumed = run_formal_five_runs(
        replace(request, resume=True),
        executor=forbidden,
        completion_evaluator=_evaluate,
    )
    assert calls == 0
    assert resumed.status == "completed"
    assert resumed.questions[0].resumed is True


def test_resume_rejects_missing_artifact_manifest(tmp_path: Path) -> None:
    request = _request(tmp_path)
    run_formal_five_runs(
        request,
        executor=lambda _context: _execution(),
        completion_evaluator=_evaluate,
    )
    batch_root = Path(request.run_root) / "T07-WB5-20260807-v2"
    (batch_root / "Q001/artifact_manifest.json").unlink()
    with pytest.raises(BatchRunnerError) as captured:
        run_formal_five_runs(replace(request, resume=True))
    assert captured.value.error_code == "ARTIFACT_MANIFEST_MISSING"


def test_resume_rejects_delivery_index_hash_mismatch(tmp_path: Path) -> None:
    request = _request(tmp_path)
    run_formal_five_runs(
        request,
        executor=lambda _context: _execution(),
        completion_evaluator=_evaluate,
    )
    index_path = Path(request.run_root) / "T07-WB5-20260807-v2/delivery_index.json"
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    payload["index_sha256"] = "f" * 64
    index_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(BatchRunnerError) as captured:
        run_formal_five_runs(replace(request, resume=True))
    assert captured.value.error_code == "DELIVERY_CHECKSUM_MISMATCH"


def test_dry_run_never_calls_executor(tmp_path: Path) -> None:
    called = False

    def forbidden(_context):
        nonlocal called
        called = True
        return _execution()

    receipt = run_formal_five_runs(
        _request(tmp_path, execute=False),
        executor=forbidden,
    )
    assert receipt.status == "dry_run"
    assert receipt.provider_calls == 0
    assert called is False


def test_default_executor_fails_before_provider_call(tmp_path: Path) -> None:
    receipt = run_formal_five_runs(_request(tmp_path))
    assert receipt.status == "failed"
    assert receipt.provider_calls == 0
    assert receipt.questions[0].error_codes == ("CALL_AUDIT_HOOK_UNAVAILABLE",)
