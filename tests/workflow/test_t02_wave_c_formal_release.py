"""Fail-closed tests for the Captain-authorized T02 Wave C formal runner."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

import app.workflow.preflight as preflight_module
import app.workflow.wave_c_release as release


GIT_SHA = "1" * 40


def _authority_payload(*, login: str = release.CAPTAIN_LOGIN) -> dict[str, Any]:
    return {
        "user": {"login": login},
        "html_url": release.CAPTAIN_AUTHORITY_URL,
        "created_at": "2026-08-14T08:13:44Z",
        "body": "\n".join(
            (
                "RANDOM_CASE_IDS=[Q095,Q045,Q100]",
                "RANDOM_CASE_SEED=20260814",
                "Q028_FLAGSHIP_SHARED_RUN_ALLOWED=YES",
                "METRIC004_RANDOM_CASE_COUNT_CONFIRMED=YES",
                "C007_LOGICAL_CASE_OBLIGATIONS=5",
                "C007_UNIQUE_ACTUAL_RUNS=4",
                "AUTHORIZED_BY_CAPTAIN=YES",
            )
        ),
    }


def test_verify_captain_authority_checks_publisher_and_all_frozen_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        observed.append(command)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(_authority_payload()),
            stderr="",
        )

    monkeypatch.setattr(release.subprocess, "run", fake_run)

    result = release.verify_captain_authority()

    assert result["verified"] is True
    assert result["login"] == "liuyanbo12"
    assert result["timestamp"] == "2026-08-14T08:13:44Z"
    assert observed == [
        [
            "gh",
            "api",
            "repos/sage125-ai-scientist-team/SAGE125-AI-Scientist/"
            "issues/comments/5291084709",
        ]
    ]

    def wrong_publisher(
        command: list[str], **_kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(_authority_payload(login="not-the-captain")),
            stderr="",
        )

    monkeypatch.setattr(release.subprocess, "run", wrong_publisher)
    with pytest.raises(ValueError, match="publisher"):
        release.verify_captain_authority()


def test_frozen_random_selection_is_exact_and_excludes_q028() -> None:
    items = [{"id": f"Q{index:03d}"} for index in range(1, 126)]

    assert release.reproduce_random_selection(items) == ["Q095", "Q045", "Q100"]

    missing = [item for item in items if item["id"] != "Q100"]
    with pytest.raises(ValueError, match="population"):
        release.reproduce_random_selection(missing)


def test_blocked_preflight_writes_four_non_mock_records_and_five_logical_rows(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    items = [
        {
            "id": f"Q{index:03d}",
            "question": f"Canonical question {index}",
            "domain": "test-only-canonical-shape",
        }
        for index in range(1, 126)
    ]
    by_id = {item["id"]: item for item in items}
    by_id["Q028"]["question"] = release.Q028_QUESTION
    source = {
        "source_document_url": release.SOURCE_DOCUMENT_URL,
        "source_document_filename": "sjtu-booklet.pdf",
        "source_document_sha256": release.SOURCE_DOCUMENT_SHA256,
        "source_catalog_sha256": release.canonical_sha256(items),
        "source_record_count": 125,
        "removed_count": 0,
        "fallback_used": False,
        "layout_repairs": [],
        "quality_issues": [],
    }
    flagship = tmp_path / "flagship.json"
    flagship.write_text('{"question_id":"Q028"}\n', encoding="utf-8")
    blocked_preflight = {
        "ok": False,
        "errors": ["real provider credentials missing"],
        "warnings": [],
        "fix_commands": ["py -3 scripts/setup_env.py"],
        "can_run_real": False,
        "can_run_mock": True,
        "connectivity": {"checked": False, "ok": None},
    }
    config = {
        "provider": "qwen",
        "models": {"fast": "qwen-fast"},
        "use_local_rag": False,
        "use_deep_research": False,
        "use_open_literature": True,
        "reviewer_auto_revision": True,
        "mock_mode": False,
        "random_seed": release.FORMAL_RANDOM_SEED,
    }
    monkeypatch.setattr(release, "verify_captain_authority", lambda: {"verified": True})
    monkeypatch.setattr(release, "_current_git_sha", lambda: GIT_SHA)
    monkeypatch.setattr(
        release,
        "load_canonical_catalog",
        lambda _path: (items, source),
    )
    monkeypatch.setattr(
        release,
        "reproduce_random_selection",
        lambda _items: list(release.FORMAL_RANDOM_CASE_IDS),
    )
    monkeypatch.setattr(release, "FLAGSHIP_SOURCE", str(flagship))
    monkeypatch.setattr(
        release,
        "Q028_CANONICAL_INPUT_HASH",
        release.canonical_sha256(by_id["Q028"]),
    )
    monkeypatch.setattr(release, "_release_config", lambda: config)
    monkeypatch.setattr(
        preflight_module,
        "run_real_preflight",
        lambda **_kwargs: blocked_preflight,
    )

    def forbidden_actual_call(**_kwargs: Any) -> Any:
        raise AssertionError("provider-blocked formal mode must not call the pipeline")

    monkeypatch.setattr(release, "execute_formal_case", forbidden_actual_call)
    output = tmp_path / "evidence"

    summary = release.run_formal_release(tmp_path / "unused.pdf", output)

    raw = json.loads((output / "raw_results.json").read_text(encoding="utf-8"))
    matrix = json.loads(
        (output / "regression_matrix.json").read_text(encoding="utf-8")
    )
    metrics = json.loads((output / "metrics.json").read_text(encoding="utf-8"))
    assert summary["raw_status"] == "BLOCKED"
    assert summary["actual_run_count"] == 0
    assert len(raw["records"]) == 4
    assert [record["question_id"] for record in raw["records"]] == [
        "Q028",
        "Q095",
        "Q045",
        "Q100",
    ]
    assert sum(record["question_id"] == "Q028" for record in raw["records"]) == 1
    assert all(record["status"] == "CASE_BLOCKED" for record in raw["records"])
    assert all(record["execution_mode"] == "real" for record in raw["records"])
    assert all(record["mock_mode"] is False for record in raw["records"])
    assert len(matrix["rows"]) == 5
    assert matrix["rows"][0]["shared_run"] is True
    assert matrix["rows"][1]["shared_run"] is True
    assert matrix["result"] == "BLOCKED"
    assert metrics["random_case_ids"] == ["Q095", "Q045", "Q100"]
    assert metrics["random_case_executed"] == 0
    assert metrics["random_case_passed"] == 0
    assert (output / "checksums.json").is_file()
    reproduction = (output / "reproduction.md").read_text(encoding="utf-8")
    assert "--execute-release" in reproduction
    assert "fixture" in reproduction
