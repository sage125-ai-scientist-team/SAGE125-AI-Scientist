"""Tests for T09-12's fail-closed, provider-free evaluation execution path."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.eval.run_t09_12_domain_actual import (
    PROTOCOL_PATH,
    _question_bindings,
    canonical_json_sha256,
    preflight,
    run,
)
from scripts.eval.validate_t09_12_domain_actual import validate


DOMAINS = [
    "mathematics", "physics", "chemistry", "biology", "medicine", "earth_science",
    "computer_science", "materials", "astronomy", "neuroscience", "climate", "engineering",
]


def _sha256(path: Path) -> str:
    """Return a deterministic digest for the test manifest's source fixture."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest(tmp_path: Path) -> Path:
    """Create a complete manifest and source using the production questions[] object shape."""
    source = tmp_path / "questions.json"
    question_ids = [f"Q{index:03d}" for index in range(1, 13)]
    question_ids[7] = "Q089"
    question_ids[11] = "Q088"
    source_items = [
        {
            "question_id": question_ids[index - 1],
            "question": f"Canonical source question {index:03d}",
            "domain": domain,
        }
        for index, domain in enumerate(DOMAINS, 1)
    ]
    source.write_text(json.dumps({"questions": source_items}), encoding="utf-8")
    domains = [
        {
            "domain": item["domain"],
            "question_id": item["question_id"],
            "question": item["question"],
            "question_sha256": hashlib.sha256(item["question"].encode("utf-8")).hexdigest(),
        }
        for item in source_items
    ]
    manifest = {
        "schema_version": "1.0",
        "question_source": {
            "path": str(source),
            "sha256": _sha256(source),
            "identity": {
                "canonical_path": str(source.resolve()),
                "sha256": _sha256(source),
            },
        },
        "domains": domains,
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def _fake_pipeline_factory(tmp_path: Path, outcomes: list[object] | None = None):
    """Build a fake pipeline that creates safe artifacts without provider transport."""
    calls: list[dict[str, object]] = []
    remaining = list(outcomes or [])

    def fake_pipeline(question_id: str, **kwargs: object) -> tuple[object, SimpleNamespace]:
        """Create a deterministic mock artifact or raise the requested test error."""
        calls.append({"question_id": question_id, **kwargs})
        if remaining:
            outcome = remaining.pop(0)
            if isinstance(outcome, BaseException):
                raise outcome
        artifact_dir = tmp_path / "pipeline-artifacts" / f"run-{question_id}"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        (artifact_dir / "report.json").write_text('{"status":"mock"}', encoding="utf-8")
        return object(), SimpleNamespace(
            run_id=f"run-{question_id}",
            llm_calls=[{"provider": "mock", "mock": True}],
        )

    return calls, fake_pipeline


def test_preflight_only_never_invokes_pipeline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The default mode writes governance artifacts and cannot reach a Provider."""
    manifest = _manifest(tmp_path)
    monkeypatch.setattr(
        "scripts.eval.run_t09_12_domain_actual.run_pipeline_with_state",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("pipeline must not run")),
    )
    report = run(manifest, tmp_path / "out")
    assert report["passed"] is True
    assert report["mode"] == "preflight-only"
    assert report["provider_calls"] == 0
    assert (tmp_path / "out" / "ledger.json").is_file()
    assert validate(PROTOCOL_PATH, tmp_path / "out" / "ledger.json")["passed"] is True


def test_mock_execution_reuses_pipeline_and_audit_without_provider(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock execution calls the shared pipeline but records zero real Provider calls."""
    manifest = _manifest(tmp_path)
    calls, fake_pipeline = _fake_pipeline_factory(tmp_path)
    monkeypatch.setattr("scripts.eval.run_t09_12_domain_actual.run_pipeline_with_state", fake_pipeline)
    monkeypatch.setattr(
        "scripts.eval.run_t09_12_domain_actual.resolve_artifact_base",
        lambda *_args: tmp_path / "pipeline-artifacts",
    )
    report = run(manifest, tmp_path / "out", execute=True, mock=True)
    assert report["passed"] is True
    assert report["provider_calls"] == 0
    assert len(calls) == 12
    assert all(call["mock_mode"] is True for call in calls)


def test_canonical_manifest_hash_ignores_json_formatting(tmp_path: Path) -> None:
    """Canonical hashing binds semantic manifest content instead of JSON whitespace."""
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    first.write_text('{"b":2,"a":[1,3]}', encoding="utf-8")
    second.write_text('{\n  "a": [1, 3],\n  "b": 2\n}', encoding="utf-8")
    assert canonical_json_sha256(first) == canonical_json_sha256(second)


def test_manifest_source_identity_rejects_mismatched_canonical_path(tmp_path: Path) -> None:
    """A manifest must bind a source identity with the resolved canonical source path."""
    manifest = _manifest(tmp_path)
    value = json.loads(manifest.read_text(encoding="utf-8"))
    value["question_source"]["identity"]["canonical_path"] = str(tmp_path / "other.json")
    manifest.write_text(json.dumps(value), encoding="utf-8")
    report = run(manifest, tmp_path / "out")
    assert report["passed"] is False
    assert "question_source_identity" in report["errors"]


def test_preflight_binds_each_question_to_source_text_domain_and_hash(tmp_path: Path) -> None:
    """The real questions[] structure provides a positive per-item source binding fixture."""
    report = preflight(_manifest(tmp_path))
    binding = report["question_source_binding"]
    assert report["passed"] is True
    assert len(binding["question_bindings_sha256"]) == 64
    assert binding["canonical_path"] == str((tmp_path / "questions.json").resolve())


def test_preflight_accepts_approved_q089_and_q088_domain_mappings(tmp_path: Path) -> None:
    """Approved source mappings retain Q089 as materials and Q088 as engineering."""
    manifest = _manifest(tmp_path)
    bindings, _ = _question_bindings(
        json.loads(manifest.read_text(encoding="utf-8"))["domains"], tmp_path / "questions.json"
    )
    assert {item["question_id"]: item["domain"] for item in bindings}["Q089"] == "materials"
    assert {item["question_id"]: item["domain"] for item in bindings}["Q088"] == "engineering"


def test_preflight_rejects_question_text_drift(tmp_path: Path) -> None:
    """A manifest cannot relabel a source question while retaining its question ID."""
    manifest = _manifest(tmp_path)
    value = json.loads(manifest.read_text(encoding="utf-8"))
    value["domains"][0]["question"] = "Changed wording"
    manifest.write_text(json.dumps(value), encoding="utf-8")
    assert "question_source_question" in preflight(manifest)["errors"]


def test_preflight_rejects_question_domain_drift(tmp_path: Path) -> None:
    """A manifest domain must equal the domain approved in its source question item."""
    manifest = _manifest(tmp_path)
    value = json.loads(manifest.read_text(encoding="utf-8"))
    value["domains"][0]["domain"] = "engineering"
    manifest.write_text(json.dumps(value), encoding="utf-8")
    assert "question_source_domain" in preflight(manifest)["errors"]


def test_preflight_rejects_question_canonical_hash_drift(tmp_path: Path) -> None:
    """A source question's UTF-8 hash is required even when its visible text matches."""
    manifest = _manifest(tmp_path)
    value = json.loads(manifest.read_text(encoding="utf-8"))
    value["domains"][0]["question_sha256"] = "0" * 64
    manifest.write_text(json.dumps(value), encoding="utf-8")
    assert "question_source_question_sha256" in preflight(manifest)["errors"]


def test_preflight_binds_sage_questions_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """SAGE_QUESTIONS_PATH must select the exact source identified by the manifest."""
    manifest = _manifest(tmp_path)
    monkeypatch.setenv("SAGE_QUESTIONS_PATH", str(tmp_path / "different.json"))
    assert "question_source_runtime_binding" in preflight(manifest)["errors"]


def test_preflight_rejects_unapproved_q089_domain_mapping(tmp_path: Path) -> None:
    """Q089 cannot change from its approved materials mapping in the source fixture."""
    manifest = _manifest(tmp_path)
    source = tmp_path / "questions.json"
    value = json.loads(source.read_text(encoding="utf-8"))
    next(item for item in value["questions"] if item["question_id"] == "Q089")["domain"] = "climate"
    source.write_text(json.dumps(value), encoding="utf-8")
    assert "question_source_approved_mapping" in preflight(manifest)["errors"]


def test_preflight_rejects_replacement_character_in_question_source(tmp_path: Path) -> None:
    """Malformed Q109 question text is rejected before any pipeline call can occur."""
    source = tmp_path / "questions.json"
    manifest = _manifest(tmp_path)
    value = json.loads(source.read_text(encoding="utf-8"))
    value["questions"][0].update(
        {"question_id": "Q109", "question": "Corrupted \ufffd question", "domain": "mathematics"}
    )
    source.write_text(json.dumps(value), encoding="utf-8")
    assert "question_replacement_characters" in preflight(manifest)["errors"]


def test_real_execution_requires_provider_configuration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-mock execution fails before transport when the Qwen provider is unavailable."""
    manifest = _manifest(tmp_path)
    monkeypatch.setattr(
        "scripts.eval.run_t09_12_domain_actual.get_settings",
        lambda: SimpleNamespace(qwen_configured=False),
    )
    report = run(manifest, tmp_path / "out", execute=True, mock=False)
    assert report["passed"] is False
    assert "provider_not_configured" in report["errors"]
    assert report["provider_calls"] == 0


def test_retry_once_only_for_transient_failure_then_resume(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A transient error receives exactly one retry and a resumed ledger makes no calls."""
    manifest = _manifest(tmp_path)
    calls, fake_pipeline = _fake_pipeline_factory(tmp_path, [TimeoutError("offline")])
    monkeypatch.setattr("scripts.eval.run_t09_12_domain_actual.run_pipeline_with_state", fake_pipeline)
    monkeypatch.setattr(
        "scripts.eval.run_t09_12_domain_actual.resolve_artifact_base",
        lambda *_args: tmp_path / "pipeline-artifacts",
    )
    report = run(manifest, tmp_path / "out", execute=True, mock=True, retry=True, attempt_cap=24)
    ledger = json.loads((tmp_path / "out" / "ledger.json").read_text(encoding="utf-8"))
    assert report["passed"] is True
    assert report["provider_calls"] == 0
    assert len(ledger["entries"][0]["attempts"]) == 2
    assert ledger["entries"][0]["attempts"][0]["retryable"] is True
    assert len(calls) == 13
    run(manifest, tmp_path / "out", execute=True, mock=True, retry=True, attempt_cap=24, resume=True)
    assert len(calls) == 13


def test_resume_rejects_question_source_binding_mismatch(tmp_path: Path) -> None:
    """Resume rejects a ledger whose separately-recorded source binding was altered."""
    manifest = _manifest(tmp_path)
    output_dir = tmp_path / "out"
    run(manifest, output_dir)
    ledger_path = output_dir / "ledger.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    ledger["question_source_binding"]["question_bindings_sha256"] = "0" * 64
    ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
    with pytest.raises(ValueError, match="resume_question_source_binding_mismatch"):
        run(manifest, output_dir, execute=True, mock=True, resume=True)


def test_non_retryable_failure_stops_the_global_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A permanent failure ends the batch immediately and preserves zero provider calls."""
    manifest = _manifest(tmp_path)
    calls, fake_pipeline = _fake_pipeline_factory(tmp_path, [ValueError("invalid input")])
    monkeypatch.setattr("scripts.eval.run_t09_12_domain_actual.run_pipeline_with_state", fake_pipeline)
    report = run(manifest, tmp_path / "out", execute=True, mock=True, retry=True)
    ledger = json.loads((tmp_path / "out" / "ledger.json").read_text(encoding="utf-8"))
    assert report["passed"] is False
    assert report["provider_calls"] == 0
    assert len(calls) == 1
    assert ledger["stopped"] is True
    assert ledger["entries"][0]["attempts"][0]["retryable"] is False


def test_attempt_cap_is_limited_to_twenty_four(tmp_path: Path) -> None:
    """The public runner rejects an attempt cap above the governed maximum."""
    with pytest.raises(ValueError, match="24"):
        run(_manifest(tmp_path), tmp_path / "out", attempt_cap=25)


def test_artifact_hash_secret_scan_and_null_cost_fields(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Artifacts are hashed, scanned, and retain unknown token and cost values as null."""
    manifest = _manifest(tmp_path)
    calls, fake_pipeline = _fake_pipeline_factory(tmp_path)
    monkeypatch.setattr("scripts.eval.run_t09_12_domain_actual.run_pipeline_with_state", fake_pipeline)
    monkeypatch.setattr(
        "scripts.eval.run_t09_12_domain_actual.resolve_artifact_base",
        lambda *_args: tmp_path / "pipeline-artifacts",
    )
    report = run(manifest, tmp_path / "out", execute=True, mock=True)
    ledger = json.loads((tmp_path / "out" / "ledger.json").read_text(encoding="utf-8"))
    completed = ledger["entries"][0]["attempts"][0]
    assert report["provider_calls"] == 0
    assert completed["artifact"]["sha256"]
    assert completed["artifact"]["secret_scan"]["passed"] is True
    assert completed["token_count"] is None
    assert completed["cost_usd"] is None


def test_preflight_rejects_source_sha_mismatch(tmp_path: Path) -> None:
    """A changed question source invalidates the manifest before any execution."""
    manifest = _manifest(tmp_path)
    value = json.loads(manifest.read_text(encoding="utf-8"))
    value["question_source"]["sha256"] = "0" * 64
    manifest.write_text(json.dumps(value), encoding="utf-8")
    report = run(manifest, tmp_path / "out")
    assert report["passed"] is False
    assert "question_source_sha256" in report["errors"]
