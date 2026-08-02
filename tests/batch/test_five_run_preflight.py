"""Fail-closed offline preflight tests for the T07-WB5 real-run gate."""

from __future__ import annotations

import subprocess
from pathlib import Path

from app.batch.five_run_preflight import (
    verify_provider_configuration_boolean,
    verify_t01_gate_availability,
    verify_t03_gate_availability,
)
from scripts.batch_125.preflight_five_real_runs import build_parser


def test_provider_configuration_returns_only_boolean() -> None:
    assert verify_provider_configuration_boolean(
        ("DASHSCOPE_API_KEY",),
        environment={"DASHSCOPE_API_KEY": "must-never-be-returned"},
    ) is True
    assert verify_provider_configuration_boolean(
        ("DASHSCOPE_API_KEY",),
        environment={},
    ) is False


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
