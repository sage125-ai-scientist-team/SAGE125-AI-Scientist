"""Fail-closed offline preflight tests for the T07-WB5 real-run gate."""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

from app.batch.five_run_preflight import (
    verify_provider_configuration_boolean,
    verify_t01_gate_availability,
    verify_t03_gate_availability,
)
from scripts.batch_125.preflight_five_real_runs import (
    _safe_provider_diagnostics,
    build_parser,
)


def test_provider_configuration_returns_only_boolean() -> None:
    assert verify_provider_configuration_boolean(
        ("DASHSCOPE_API_KEY",),
        environment={"DASHSCOPE_API_KEY": "must-never-be-returned"},
    ) is True
    assert verify_provider_configuration_boolean(
        ("DASHSCOPE_API_KEY",),
        environment={},
    ) is False


def test_cli_provider_diagnostics_are_loader_backed_and_secret_free(
    tmp_path: Path,
) -> None:
    (tmp_path / ".env").write_text("must-not-be-read-by-test\n", encoding="utf-8")
    sentinel_secret = "must-never-be-returned"

    diagnostics = _safe_provider_diagnostics(
        tmp_path,
        environment={"MOCK_LLM": "false"},
        settings_loader=lambda: SimpleNamespace(
            llm_provider="bailian",
            qwen_configured=True,
            deep_research_configured=False,
            dashscope_api_key=sentinel_secret,
        ),
    )

    assert diagnostics == {
        "env_file_exists": True,
        "provider_name": "bailian",
        "qwen_configured": True,
        "deep_research_configured": False,
        "mock_mode_enabled": False,
        "config_loader_invoked": True,
    }
    assert sentinel_secret not in repr(diagnostics)


def test_t01_commit_not_in_head_is_stably_blocked(tmp_path: Path) -> None:
    calls: list[tuple[str, ...]] = []

    def unavailable(command: tuple[str, ...], cwd: Path):
        calls.append(command)
        return subprocess.CompletedProcess(command, 128, "", "unknown commit")

    result = verify_t01_gate_availability(
        "a" * 40,
        tmp_path,
        git_runner=unavailable,
    )

    assert not result.available
    assert result.code == "T01_GATE_VERSION_UNAVAILABLE"
    assert calls == [("git", "merge-base", "--is-ancestor", "a" * 40, "HEAD")]


def test_t01_non_ancestor_commit_is_stably_blocked(tmp_path: Path) -> None:
    def non_ancestor(command: tuple[str, ...], cwd: Path):
        return subprocess.CompletedProcess(command, 1, "", "")

    result = verify_t01_gate_availability(
        "a" * 40,
        tmp_path,
        git_runner=non_ancestor,
    )

    assert not result.available
    assert result.code == "T01_GATE_VERSION_UNAVAILABLE"


def test_t01_ancestor_and_callable_interface_are_available(
    tmp_path: Path,
) -> None:
    def ancestor(command: tuple[str, ...], cwd: Path):
        return subprocess.CompletedProcess(command, 0, "", "")

    module = SimpleNamespace(precheck_bundle_for_validation=lambda value: value)
    result = verify_t01_gate_availability(
        "a" * 40,
        tmp_path,
        git_runner=ancestor,
        import_module=lambda name: module,
    )

    assert result.available
    assert result.code == "T01_GATE_AVAILABLE"


def test_t01_commit_must_have_public_interface_even_when_ancestor(
    tmp_path: Path,
) -> None:
    def ancestor(command: tuple[str, ...], cwd: Path):
        return subprocess.CompletedProcess(command, 0, "", "")

    result = verify_t01_gate_availability(
        "a" * 40,
        tmp_path,
        git_runner=ancestor,
        import_module=lambda name: object(),
    )

    assert not result.available
    assert result.code == "T01_INTERFACE_UNAVAILABLE"


def test_t01_public_interface_must_be_callable(tmp_path: Path) -> None:
    def ancestor(command: tuple[str, ...], cwd: Path):
        return subprocess.CompletedProcess(command, 0, "", "")

    module = SimpleNamespace(precheck_bundle_for_validation=object())
    result = verify_t01_gate_availability(
        "a" * 40,
        tmp_path,
        git_runner=ancestor,
        import_module=lambda name: module,
    )

    assert not result.available
    assert result.code == "T01_INTERFACE_UNAVAILABLE"


def test_current_t03_public_interfaces_are_available() -> None:
    result = verify_t03_gate_availability()

    assert result.available
    assert result.code == "T03_GATE_AVAILABLE"


def test_cli_is_offline_unless_provider_flag_is_explicit() -> None:
    assert build_parser().parse_args([]).execute_provider_preflight is False
    assert (
        build_parser()
        .parse_args(["--execute-provider-preflight"])
        .execute_provider_preflight
        is True
    )
