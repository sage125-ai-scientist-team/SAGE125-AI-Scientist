"""Wave B deterministic, question-owned output-path tests."""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

import pytest

from app.batch.errors import BatchRunnerError


def _api():
    import app.batch.output_layout as output_layout

    return output_layout


def test_different_question_ids_have_unique_directories(tmp_path: Path) -> None:
    api = _api()
    left = api.build_question_output_paths(tmp_path / "batch", "Q001")
    right = api.build_question_output_paths(tmp_path / "batch", "Q002")

    assert left.question_root != right.question_root
    assert set(api.list_required_artifact_paths(left)).isdisjoint(
        api.list_required_artifact_paths(right)
    )


def test_same_inputs_build_deterministic_fixed_tree(tmp_path: Path) -> None:
    api = _api()
    first = api.build_question_output_paths(tmp_path / "batch", "Q001")
    second = api.build_question_output_paths(tmp_path / "batch", "Q001")

    assert first == second
    assert first.question_root == tmp_path / "batch" / "Q001"
    assert first.artifact_manifest_json.name == "artifact_manifest.json"
    assert [path.name for path in api.list_required_artifact_paths(first)] == [
        "report.pdf",
        "report.md",
        "result.json",
        "evidence_cards.json",
        "agent_trace.json",
    ]


@pytest.mark.parametrize(
    "unsafe",
    ["../evil", "Q001/other", r"Q001\other", ".", "..", " Q001"],
)
def test_unsafe_question_id_is_rejected(unsafe: str) -> None:
    with pytest.raises(BatchRunnerError) as captured:
        _api().validate_question_id_for_path(unsafe)

    assert captured.value.error_code == "OUTPUT_PATH_INVALID"


def test_absolute_output_path_is_rejected(tmp_path: Path) -> None:
    absolute = (tmp_path / "outside" / "report.pdf").resolve()

    with pytest.raises(BatchRunnerError) as captured:
        _api().validate_output_path_boundary(
            tmp_path / "batch", "Q001", absolute
        )

    assert captured.value.error_code == "OUTPUT_PATH_INVALID"


def test_retry_cannot_reuse_another_question_directory(tmp_path: Path) -> None:
    api = _api()
    paths = api.build_question_output_paths(tmp_path / "batch", "Q001")

    with pytest.raises(BatchRunnerError) as captured:
        api.create_question_output_directory(
            paths,
            expected_question_id="Q002",
        )

    assert captured.value.error_code == "OUTPUT_PATH_INVALID"


def test_tampered_paths_fail_closed(tmp_path: Path) -> None:
    api = _api()
    paths = api.build_question_output_paths(tmp_path / "batch", "Q001")
    forged = replace(paths, question_root=tmp_path / "batch" / "Q002")

    with pytest.raises(BatchRunnerError) as captured:
        api.create_question_output_directory(forged)

    assert captured.value.error_code == "OUTPUT_PATH_INVALID"


def test_cross_question_relative_path_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(BatchRunnerError) as captured:
        _api().validate_output_path_boundary(
            tmp_path / "batch",
            "Q001",
            "Q002/report.pdf",
        )

    assert captured.value.error_code == "OUTPUT_PATH_INVALID"


def test_batch_root_escape_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(BatchRunnerError) as captured:
        _api().validate_output_path_boundary(
            tmp_path / "batch",
            "Q001",
            "Q001/../../outside/report.pdf",
        )

    assert captured.value.error_code == "OUTPUT_PATH_INVALID"


def test_symlink_question_target_is_rejected(tmp_path: Path) -> None:
    batch_root = tmp_path / "batch"
    batch_root.mkdir()
    external = tmp_path / "external"
    external.mkdir()
    link = batch_root / "Q001"
    try:
        os.symlink(external, link, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")

    paths = _api().build_question_output_paths(batch_root, "Q001")
    with pytest.raises(BatchRunnerError) as captured:
        _api().create_question_output_directory(paths)

    assert captured.value.error_code == "ARTIFACT_SYMLINK_REJECTED"


def test_symlink_question_detection_is_verified_without_os_privilege(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = _api()
    paths = api.build_question_output_paths(tmp_path / "batch", "Q001")
    paths.batch_root.mkdir()
    original = Path.is_symlink

    def simulated_symlink(candidate: Path) -> bool:
        return candidate == paths.question_root or original(candidate)

    monkeypatch.setattr(Path, "is_symlink", simulated_symlink)

    with pytest.raises(BatchRunnerError) as captured:
        api.create_question_output_directory(paths)

    assert captured.value.error_code == "ARTIFACT_SYMLINK_REJECTED"


@pytest.mark.parametrize(
    "reserved",
    ["CON", "nul.txt", "COM1", "LPT9.json"],
)
def test_windows_reserved_question_ids_are_rejected(reserved: str) -> None:
    with pytest.raises(BatchRunnerError) as captured:
        _api().validate_question_id_for_path(reserved)

    assert captured.value.error_code == "OUTPUT_PATH_INVALID"
