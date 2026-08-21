"""Offline tests for the formal five-question actual runner.

These tests must not call a provider.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.formal125.authorization import Formal125AuthorizationError, require_actual_authorization
from app.formal125.actual_run import (
    FORMAL_5_CASE_IDS,
    MAX_TOTAL_PROVIDER_CALLS,
    build_authorization_payload,
    classify_question_status,
    leak_hits,
    package_question,
    run_formal_five_actual,
    similarity_ratio,
    write_captain_authorization,
    write_no_clobber_json,
)


def _auth(tmp_path: Path) -> dict:
    return build_authorization_payload(
        authorization_id="formal5-test-authorization",
        case_ids=FORMAL_5_CASE_IDS,
        producer_git_sha="a" * 40,
        output_root=tmp_path,
        expires_at="2099-01-01T00:00:00+00:00",
        created_at="2026-08-21T00:00:00+00:00",
    )


def _plan(question_id: str, question: str, *, extra_results: str = "") -> dict:
    return {
        "question_id": question_id,
        "input_question": question,
        "domain": "Mathematical Sciences",
        "paper_title": f"{question_id} plan",
        "paper_abstract": "A test-only research plan.",
        "problem_statement": question,
        "rationale": "Offline packaging test.",
        "technical_details": "No provider call.",
        "methods": "Structured evidence synthesis.",
        "datasets": {"source": "open literature", "target": "held-out evaluation"},
        "experiments": {
            "baselines": ["literature baseline"],
            "metrics": ["coverage"],
            "ablation": "none",
            "validation_protocol": "not executed",
        },
        "results": "当前状态：待执行验证实验。系统已生成可复现实验脚本、数据字段清单与评价指标，尚未运行真实实验。"
        + extra_results,
        "actual_execution": False,
        "validation_status": "needs_data",
        "generated_hypotheses": [],
        "references": [],
        "reviewer_comments": [],
        "revision_history": [],
        "reproducibility_checklist": ["pin inputs"],
    }


def _state(plan: dict, *, mock: bool = False, booklet: bool = False, request_id: str | None = "req-1") -> SimpleNamespace:
    cards = []
    if booklet:
        cards.append(
            {
                "id": "EV-BOOKLET",
                "source_type": "booklet",
                "title": "sjtu-booklet.pdf",
                "authors": [],
                "year": None,
                "url": None,
                "doi": None,
                "quoted_text": "question source",
                "summary": "booklet",
                "relevance_score": 0.1,
                "reliability_note": "source_role=question_source",
            }
        )
    records = [
        {
            "call_id": "c1",
            "provider": "mock" if mock else "bailian_qwen",
            "mock": mock,
            "status": "success",
            "request_id": None if mock else request_id,
            "input_tokens": 10,
            "output_tokens": 4,
            "model_name_internal": "qwen3.6-flash",
            "agent_name": "question_parser",
        }
    ]
    return SimpleNamespace(
        retrieved_evidence=cards,
        agent_trace=[{"agent_name": "question_parser", "status": "completed", "model_name": "qwen3.6-flash"}],
        llm_calls=records,
        quality_gates={"passed": True, "errors": [], "warnings": [], "gates": {}},
        run_mode="mock" if mock else "real",
        hypothesis_generation=None,
        evidence_extraction=None,
        execution_metadata={"actual_execution": False},
    )


def test_authorization_hash_roundtrip(tmp_path: Path) -> None:
    payload = _auth(tmp_path)
    path = tmp_path / "authorization.json"
    write_no_clobber_json(path, payload)
    loaded = require_actual_authorization(path)
    assert loaded.authorization_hash == payload["authorization_hash"]
    assert loaded.authorized_case_ids == list(FORMAL_5_CASE_IDS)


def test_authorization_no_clobber_rejects_different_payload(tmp_path: Path) -> None:
    payload = _auth(tmp_path)
    path = tmp_path / "authorization.json"
    write_no_clobber_json(path, payload)
    other = dict(payload)
    other["authorization_id"] = "formal5-test-authorization-other"
    del other["authorization_hash"]
    from app.formal125.authorization import compute_authorization_hash

    other["authorization_hash"] = compute_authorization_hash(other)
    with pytest.raises(Formal125AuthorizationError, match="no-clobber"):
        write_no_clobber_json(path, other)
    write_no_clobber_json(path, payload)


def test_missing_authorization_does_not_execute(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"pipeline": False}

    def _pipeline(question_id: str, **kwargs):
        called["pipeline"] = True
        raise AssertionError("provider boundary must not be crossed")

    with pytest.raises(Formal125AuthorizationError):
        run_formal_five_actual(
            repo_root=tmp_path,
            output_root=tmp_path / "run",
            authorization_path=tmp_path / "missing.json",
            execute=True,
            pipeline_fn=_pipeline,
            install_runtime=False,
        )
    assert called["pipeline"] is False


def test_classify_and_leak_rules() -> None:
    assert (
        classify_question_status(
            pipeline_ok=True,
            required_present=True,
            blocking_p0=0,
            blocking_p1=0,
            mock_calls=0,
            booklet_contamination=0,
            auth_failed=False,
            budget_exceeded=False,
            actual_execution=False,
            leak_count=0,
        )
        == "succeeded"
    )
    assert (
        classify_question_status(
            pipeline_ok=True,
            required_present=True,
            blocking_p0=0,
            blocking_p1=0,
            mock_calls=1,
            booklet_contamination=0,
            auth_failed=False,
            budget_exceeded=False,
            actual_execution=False,
            leak_count=0,
        )
        == "partial"
    )
    assert leak_hits("Q001", "copied WDBC pipeline")
    assert leak_hits("Q028", "WDBC")
    assert not leak_hits("Q001", "prime numbers and cryptography")


def test_package_question_writes_nine_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.formal125 import actual_run as module

    def _pdf(markdown_path: Path, pdf_path: Path) -> dict:
        pdf_path.write_bytes(b"%PDF-1.4 test\n")
        return {"status": "ok", "engine": "test"}

    monkeypatch.setattr(module, "export_markdown_to_pdf", _pdf)
    plan = _plan("Q001", "What makes prime numbers so special?")
    packaged = package_question(
        question_dir=tmp_path / "Q001",
        question_id="Q001",
        plan=plan,
        state=_state(plan),
        previous_texts={},
        batch_calls=0,
        batch_input=0,
        batch_output=0,
    )
    names = [
        "result.md",
        "result.json",
        "result.pdf",
        "evidence_cards.json",
        "agent_trace.json",
        "validation.json",
        "provider_audit.json",
        "package_manifest.json",
        "checksums.sha256",
    ]
    for name in names:
        path = tmp_path / "Q001" / name
        assert path.is_file() and path.stat().st_size > 0
    assert packaged["required_present"] is True
    assert packaged["status"] in {"succeeded", "partial"}
    audit = json.loads((tmp_path / "Q001" / "provider_audit.json").read_text(encoding="utf-8"))
    assert audit["estimated_cost"] == "unknown"
    dumped = json.dumps(audit)
    assert "sk-" not in dumped
    assert "DASHSCOPE_API_KEY" not in dumped


def test_mock_and_booklet_cannot_succeed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.formal125 import actual_run as module

    def _pdf(markdown_path: Path, pdf_path: Path) -> dict:
        pdf_path.write_bytes(b"%PDF-1.4 test\n")
        return {"status": "ok", "engine": "test"}

    monkeypatch.setattr(module, "export_markdown_to_pdf", _pdf)
    plan = _plan("Q001", "What makes prime numbers so special?")
    mocked = package_question(
        question_dir=tmp_path / "mock",
        question_id="Q001",
        plan=plan,
        state=_state(plan, mock=True),
        previous_texts={},
        batch_calls=0,
        batch_input=0,
        batch_output=0,
    )
    assert mocked["status"] != "succeeded"
    contaminated = package_question(
        question_dir=tmp_path / "booklet",
        question_id="Q001",
        plan=plan,
        state=_state(plan, booklet=True),
        previous_texts={},
        batch_calls=0,
        batch_input=0,
        batch_output=0,
    )
    assert contaminated["status"] != "succeeded"
    assert contaminated["validation"]["booklet_contamination_count"] >= 1


def test_similarity_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.formal125 import actual_run as module

    def _pdf(markdown_path: Path, pdf_path: Path) -> dict:
        pdf_path.write_bytes(b"%PDF-1.4 test\n")
        return {"status": "ok", "engine": "test"}

    monkeypatch.setattr(module, "export_markdown_to_pdf", _pdf)
    text = "A unique climate-policy research plan about radiative forcing and carbon budgets. " * 20
    first = package_question(
        question_dir=tmp_path / "Q001",
        question_id="Q001",
        plan=_plan("Q001", "What makes prime numbers so special?", extra_results=text),
        state=_state(_plan("Q001", "What makes prime numbers so special?")),
        previous_texts={},
        batch_calls=0,
        batch_input=0,
        batch_output=0,
    )
    second = package_question(
        question_dir=tmp_path / "Q028",
        question_id="Q028",
        plan=_plan("Q028", "Will it be possible to cure all cancers?", extra_results=text),
        state=_state(_plan("Q028", "Will it be possible to cure all cancers?")),
        previous_texts={"Q001": first["result_text"]},
        batch_calls=0,
        batch_input=0,
        batch_output=0,
    )
    assert similarity_ratio(first["result_text"], second["result_text"]) > 0.90
    assert second["validation"]["manual_review_required"] is True


def test_serial_fake_batch_updates_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.formal125 import actual_run as module

    monkeypatch.setattr(module, "git_head", lambda repo_root: "b" * 40)
    monkeypatch.setattr(module, "materialize_questions", lambda destination: destination.write_text("[]", encoding="utf-8") or destination)
    def _pdf(markdown_path: Path, pdf_path: Path) -> dict:
        pdf_path.write_bytes(b"%PDF-1.4 test\n")
        return {"status": "ok", "engine": "test"}

    monkeypatch.setattr(module, "export_markdown_to_pdf", _pdf)
    auth = _auth(tmp_path / "run")
    auth_path = tmp_path / "run" / "authorization.json"
    write_no_clobber_json(auth_path, auth)
    seen: list[str] = []

    def _pipeline(question_id: str, **kwargs):
        seen.append(question_id)
        plan = _plan(question_id, f"question {question_id}")
        return plan, _state(plan)

    summary = run_formal_five_actual(
        repo_root=tmp_path,
        output_root=tmp_path / "run",
        authorization_path=auth_path,
        execute=True,
        pipeline_fn=_pipeline,
        install_runtime=False,
    )
    assert seen == list(FORMAL_5_CASE_IDS)
    manifest = json.loads((tmp_path / "run" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["total"] == 5
    assert sum(manifest["status_counts"].values()) == 5
    assert summary["estimated_cost"] == "unknown"
    assert summary["project_provider_calls_before"] == 6


def test_budget_pause_blocks_remaining(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.formal125 import actual_run as module

    monkeypatch.setattr(module, "git_head", lambda repo_root: "b" * 40)
    monkeypatch.setattr(module, "materialize_questions", lambda destination: destination.write_text("[]", encoding="utf-8") or destination)
    def _pdf(markdown_path: Path, pdf_path: Path) -> dict:
        pdf_path.write_bytes(b"%PDF-1.4 test\n")
        return {"status": "ok", "engine": "test"}

    monkeypatch.setattr(module, "export_markdown_to_pdf", _pdf)
    original_budget = module.budget_snapshot

    def _budget(*, calls: int, input_tokens: int, output_tokens: int):
        payload = original_budget(calls=calls, input_tokens=input_tokens, output_tokens=output_tokens)
        if calls >= 1:
            payload = dict(payload)
            payload["state"] = "pause_after_current"
        return payload

    monkeypatch.setattr(module, "budget_snapshot", _budget)
    auth = _auth(tmp_path / "run")
    auth_path = tmp_path / "run" / "authorization.json"
    write_no_clobber_json(auth_path, auth)

    def _pipeline(question_id: str, **kwargs):
        plan = _plan(question_id, f"question {question_id}")
        return plan, _state(plan)

    summary = run_formal_five_actual(
        repo_root=tmp_path,
        output_root=tmp_path / "run",
        authorization_path=auth_path,
        execute=True,
        pipeline_fn=_pipeline,
        install_runtime=False,
    )
    manifest = json.loads((tmp_path / "run" / "manifest.json").read_text(encoding="utf-8"))
    blocked = sum(1 for item in manifest["questions"].values() if item["status"] == "blocked")
    assert blocked >= 1
    assert summary["status_counts"]["blocked"] >= 1


def test_write_captain_authorization_binds_head(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.formal125 import actual_run as module

    monkeypatch.setattr(module, "git_head", lambda repo_root: "c" * 40)
    result = write_captain_authorization(
        repo_root=tmp_path,
        output_root=tmp_path / "run",
        authorization_id="formal5-test-bind",
    )
    assert result["producer_git_sha"] == "c" * 40
    auth = json.loads((tmp_path / "run" / "authorization" / "authorization.json").read_text(encoding="utf-8"))
    receipt = json.loads(
        (tmp_path / "run" / "authorization" / "captain_authorization_receipt.json").read_text(encoding="utf-8")
    )
    assert auth["max_total_provider_calls"] == MAX_TOTAL_PROVIDER_CALLS
    assert receipt["authorized_by_account"] == "liuyanbo12"
    assert receipt["producer_git_sha"] == "c" * 40
    dumped = json.dumps(auth) + json.dumps(receipt)
    assert "sk-" not in dumped
    assert "DASHSCOPE" not in dumped
