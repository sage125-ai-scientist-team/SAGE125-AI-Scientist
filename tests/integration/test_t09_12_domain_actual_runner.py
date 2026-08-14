"""Batch 4B formal-schema tests for the provider-free T09 domain runner."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.eval.run_t09_12_domain_actual import (
    FORMAL_QUESTION_SOURCE_PATH,
    FORMAL_QUESTION_SOURCE_SHA256,
    PROJECT_ROOT,
    canonical_input_hash,
    canonical_json_sha256,
    preflight,
    run,
)
from scripts.eval.validate_t09_12_domain_actual import validate
import scripts.eval.run_t09_12_domain_actual as runner


REPOSITORY_ROOT = PROJECT_ROOT


@pytest.fixture(autouse=True)
def isolated_formal_question_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Provide a complete temporary source so runner tests need no external booklet file."""
    source_path = tmp_path / FORMAL_QUESTION_SOURCE_PATH
    source_path.parent.mkdir(parents=True)
    items = [
        {
            "id": f"Q{number:03d}",
            "question": f"Temporary formal question Q{number:03d}",
            "domain": "Temporary Formal Domain",
        }
        for number in range(1, 126)
    ]
    items_by_id = {str(item["id"]): item for item in items}
    for _normalized_domain, (question_id, source_domain, _mapping_basis) in (
        runner.APPROVED_DOMAIN_MAPPINGS.items()
    ):
        items_by_id[question_id]["domain"] = source_domain
    source_path.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(runner, "FORMAL_QUESTION_SOURCE_SHA256", hashlib.sha256(
        source_path.read_bytes()
    ).hexdigest())
    monkeypatch.setenv("SAGE_QUESTIONS_PATH", str(source_path))


def _source_items() -> dict[str, dict[str, object]]:
    """Load the isolated formal source without altering its authoritative text."""
    value = json.loads(
        (runner.PROJECT_ROOT / runner.FORMAL_QUESTION_SOURCE_PATH).read_text(encoding="utf-8")
    )
    assert isinstance(value, list)
    return {str(item["id"]): item for item in value}


def _manifest(tmp_path: Path) -> Path:
    """Write a portable approved manifest from the isolated top-level list."""
    source = _source_items()
    domains = []
    for normalized_domain, (
        question_id,
        source_domain,
        mapping_basis,
    ) in runner.APPROVED_DOMAIN_MAPPINGS.items():
        item = source[question_id]
        question = str(item["question"])
        domains.append(
            {
                "question_id": question_id,
                "question": question,
                "source_domain": source_domain,
                "normalized_domain": normalized_domain,
                "domain": normalized_domain,
                "mapping_basis": mapping_basis,
                "approval_source": runner.APPROVAL_SOURCE,
                "canonical_input_hash": canonical_input_hash(
                    question_id, question, source_domain, normalized_domain
                ),
            }
        )
    manifest = {
        "schema_version": "1.1",
        "question_source": {
            "path": runner.FORMAL_QUESTION_SOURCE_PATH,
            "sha256": runner.FORMAL_QUESTION_SOURCE_SHA256,
        },
        "domains": domains,
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return path


def _rewrite(path: Path, mutate: object) -> None:
    """Apply one test mutation to a manifest JSON object."""
    value = json.loads(path.read_text(encoding="utf-8"))
    assert callable(mutate)
    mutate(value)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _assert_preflight_failure_without_pipeline(
    manifest: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: str
) -> None:
    """Assert every invalid manifest stops before any pipeline or Provider activity."""
    calls: list[object] = []
    monkeypatch.setattr(
        "scripts.eval.run_t09_12_domain_actual.run_pipeline_with_state",
        lambda *_args, **_kwargs: calls.append(object()),
    )
    report = run(manifest, tmp_path / "out")
    assert report["passed"] is False
    assert error in report["errors"]
    assert report["provider_calls"] == 0
    assert calls == []


def test_formal_source_is_top_level_complete_list_with_fixed_digest() -> None:
    """Verify the optional production source independently when it is available."""
    source_path = REPOSITORY_ROOT / FORMAL_QUESTION_SOURCE_PATH
    if not source_path.is_file():
        pytest.skip("正式 questions_125.json 缺失；CI 使用隔离的临时夹具")
    raw = json.loads(source_path.read_text(encoding="utf-8"))
    assert isinstance(raw, list)
    assert len(raw) == 125
    assert {item["id"] for item in raw} == {f"Q{number:03d}" for number in range(1, 126)}
    assert len({item["id"] for item in raw}) == 125
    assert hashlib.sha256(source_path.read_bytes()).hexdigest() == FORMAL_QUESTION_SOURCE_SHA256


def test_preflight_accepts_complete_approved_manifest(tmp_path: Path) -> None:
    """Approved source and normalized fields pass without executing a pipeline."""
    manifest = _manifest(tmp_path)
    report = preflight(manifest)
    assert report["passed"] is True
    assert report["provider_calls"] == 0
    assert report["question_source_binding"]["source_path"] == runner.FORMAL_QUESTION_SOURCE_PATH
    assert Path(str(report["question_source_binding"]["resolved_path"])).is_absolute()


def test_source_and_normalized_domains_can_differ_when_approved(tmp_path: Path) -> None:
    """The formal source labels are preserved instead of forced to the normalized taxonomy."""
    manifest = _manifest(tmp_path)
    value = json.loads(manifest.read_text(encoding="utf-8"))
    entry = next(item for item in value["domains"] if item["normalized_domain"] == "materials")
    assert entry["question_id"] == "Q089"
    assert entry["source_domain"] == "Engineering & Materials Science"
    assert entry["normalized_domain"] == "materials"
    assert preflight(manifest)["passed"] is True


@pytest.mark.parametrize(
    ("field", "replacement", "error"),
    [
        ("source_domain", "Changed domain", "question_source_domain"),
        ("normalized_domain", "physics", "question_source_approved_mapping"),
        ("mapping_basis", "unapproved", "question_source_approved_mapping"),
        ("approval_source", "unapproved", "approval_source"),
        ("canonical_input_hash", "0" * 64, "canonical_input_hash"),
    ],
)
def test_preflight_rejects_manifest_field_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str, replacement: str, error: str
) -> None:
    """Every approved per-entry field is immutable before execution."""
    manifest = _manifest(tmp_path)
    _rewrite(manifest, lambda value: value["domains"][0].__setitem__(field, replacement))
    _assert_preflight_failure_without_pipeline(manifest, tmp_path, monkeypatch, error)


def test_preflight_rejects_q088_q089_swap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Materials and engineering retain the current approved Q089/Q088 assignment."""
    manifest = _manifest(tmp_path)

    def swap(value: dict[str, object]) -> None:
        """Exchange IDs only, yielding an unauthorized mapping."""
        entries = value["domains"]
        assert isinstance(entries, list)
        materials = next(item for item in entries if item["normalized_domain"] == "materials")
        engineering = next(item for item in entries if item["normalized_domain"] == "engineering")
        materials["question_id"], engineering["question_id"] = (
            engineering["question_id"],
            materials["question_id"],
        )

    _rewrite(manifest, swap)
    _assert_preflight_failure_without_pipeline(
        manifest, tmp_path, monkeypatch, "question_source_approved_mapping"
    )


def test_q109_exact_source_text_passes_and_rewrite_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Q109 uses exact source text; any character rewrite is prohibited."""
    manifest = _manifest(tmp_path)
    value = json.loads(manifest.read_text(encoding="utf-8"))
    q109 = next(item for item in value["domains"] if item["question_id"] == "Q109")
    assert preflight(manifest)["passed"] is True
    q109["question"] = f"{q109['question']}?"
    q109["canonical_input_hash"] = canonical_input_hash(
        q109["question_id"], q109["question"], q109["source_domain"], q109["normalized_domain"]
    )
    manifest.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    _assert_preflight_failure_without_pipeline(
        manifest, tmp_path, monkeypatch, "question_source_question"
    )


def test_absolute_manifest_source_path_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A portable manifest never embeds a machine-specific source path."""
    manifest = _manifest(tmp_path)
    _rewrite(
        manifest,
        lambda value: value["question_source"].__setitem__(
            "path", str((runner.PROJECT_ROOT / runner.FORMAL_QUESTION_SOURCE_PATH).resolve())
        ),
    )
    _assert_preflight_failure_without_pipeline(manifest, tmp_path, monkeypatch, "question_source_sha256")


def test_runtime_source_mismatch_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An environment override must resolve to the exact formal source."""
    manifest = _manifest(tmp_path)
    monkeypatch.setenv("SAGE_QUESTIONS_PATH", str(tmp_path / "different.json"))
    _assert_preflight_failure_without_pipeline(
        manifest, tmp_path, monkeypatch, "question_source_runtime_binding"
    )


def test_preflight_fails_closed_when_formal_source_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A missing canonical source returns a failed preflight without pipeline activity."""
    manifest = _manifest(tmp_path)
    missing_source = tmp_path / "missing" / "questions_125.json"
    monkeypatch.setattr(runner, "PROJECT_ROOT", missing_source.parents[2])
    monkeypatch.setenv("SAGE_QUESTIONS_PATH", str(missing_source))
    _assert_preflight_failure_without_pipeline(
        manifest, tmp_path, monkeypatch, "question_source_sha256"
    )


def test_canonical_manifest_hash_ignores_formatting(tmp_path: Path) -> None:
    """Canonical manifest identity depends on JSON content, not whitespace."""
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    first.write_text('{"b":2,"a":[1,3]}', encoding="utf-8")
    second.write_text('{\n  "a": [1, 3],\n  "b": 2\n}', encoding="utf-8")
    assert canonical_json_sha256(first) == canonical_json_sha256(second)


def test_preflight_ledger_passes_offline_validator(tmp_path: Path) -> None:
    """The preflight-only ledger records portable and resolved source evidence."""
    manifest = _manifest(tmp_path)
    report = run(manifest, tmp_path / "out")
    assert report["passed"] is True
    assert report["mode"] == "preflight-only"
    assert validate(
        REPOSITORY_ROOT / "docs/reproducibility/T09_12_DOMAIN_SCORING_PROTOCOL.json",
        tmp_path / "out" / "ledger.json",
    )["passed"] is True


def test_formal_execute_is_blocked_without_protocol_authorization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unapproved formal execute request stops before provider or pipeline activity."""
    manifest = _manifest(tmp_path)
    calls: list[object] = []
    monkeypatch.setattr(
        runner,
        "run_pipeline_with_state",
        lambda *_args, **_kwargs: calls.append(object()),
    )
    monkeypatch.setattr(
        runner,
        "load_json",
        lambda path: {
            **json.loads(path.read_text(encoding="utf-8")),
            "actual_execution_authorization": {"authorized": False},
        } if path == runner.PROTOCOL_PATH else json.loads(path.read_text(encoding="utf-8")),
    )
    report = run(manifest, tmp_path / "out", execute=True)
    assert report["passed"] is False
    assert "actual_execution_not_authorized" in report["errors"]
    assert report["executed"] is False
    assert calls == []


def test_formal_execute_rejects_mock_before_pipeline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mock mode cannot bypass the formal actual-execution identity gate."""
    manifest = _manifest(tmp_path)
    calls: list[object] = []
    monkeypatch.setattr(
        runner,
        "run_pipeline_with_state",
        lambda *_args, **_kwargs: calls.append(object()),
    )
    report = run(manifest, tmp_path / "out", execute=True, mock=True)
    assert report["passed"] is False
    assert "formal_execution_rejects_mock" in report["errors"]
    assert calls == []


def test_validator_rejects_tampered_global_attempt_count(tmp_path: Path) -> None:
    """The offline validator recomputes the global attempt ledger on every review."""
    manifest = _manifest(tmp_path)
    run(manifest, tmp_path / "out")
    ledger_path = tmp_path / "out" / "ledger.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    ledger["global_attempt_count"] = 1
    ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
    report = validate(
        REPOSITORY_ROOT / "docs/reproducibility/T09_12_DOMAIN_SCORING_PROTOCOL.json",
        ledger_path,
    )
    assert report["passed"] is False
    assert "global_attempt_count" in report["errors"]
