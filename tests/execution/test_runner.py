"""Red tests for the controlled local process runner."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable

import pytest
from pydantic import ValidationError


def _api(
    require_symbol: Callable[[str, str, str], Any],
    test_id: str,
) -> tuple[Any, Any, Any]:
    execution_spec = require_symbol(
        "app.contracts.execution", "ExecutionSpec", test_id
    )
    registry_type = require_symbol("app.execution", "EntrypointRegistry", test_id)
    runner_type = require_symbol("app.execution", "LocalProcessRunner", test_id)
    return execution_spec, registry_type, runner_type


def _runner(
    require_symbol: Callable[[str, str, str], Any],
    test_id: str,
    managed_root: Path,
    probe_script: Path,
    *,
    entrypoint_id: str = "probe",
    script_path: Path | None = None,
    entrypoint_class: str = "test",
    allowed_environment: tuple[str, ...] = (),
    cleanup: Callable[[Path], None] | None = None,
) -> tuple[Any, Any]:
    _execution_spec, registry_type, runner_type = _api(require_symbol, test_id)
    registry = registry_type()
    registry.register_python(
        entrypoint_id,
        script_path or probe_script,
        entrypoint_class=entrypoint_class,
        allowed_environment=allowed_environment,
    )
    runner = runner_type(
        registry=registry,
        managed_root=managed_root,
        dataset_resolver=None,
        dependency_version_provider=None,
        git_provenance_provider=None,
        cleanup=cleanup,
    )
    return registry, runner


def _run(
    require_symbol: Callable[[str, str, str], Any],
    test_id: str,
    execution_spec_payload: Callable[..., dict[str, Any]],
    managed_root: Path,
    probe_script: Path,
    *,
    allowed_environment: tuple[str, ...] = (),
    cleanup: Callable[[Path], None] | None = None,
    **spec_overrides: Any,
) -> Any:
    execution_spec, _registry_type, _runner_type = _api(require_symbol, test_id)
    _registry, runner = _runner(
        require_symbol,
        test_id,
        managed_root,
        probe_script,
        allowed_environment=allowed_environment,
        cleanup=cleanup,
    )
    spec = execution_spec.model_validate(
        execution_spec_payload(**spec_overrides)
    )
    return runner.run(spec)


def test_T05_A_CMD_001_registered_python_entrypoint_is_the_only_command_source(
    require_symbol: Callable[[str, str, str], Any],
    execution_spec_payload: Callable[..., dict[str, Any]],
    managed_root: Path,
    probe_script: Path,
) -> None:
    """T05-A-CMD-001: a registry ID, not caller executable text, selects Python."""

    test_id = "T05-A-CMD-001"
    execution_spec, _registry_type, _runner_type = _api(require_symbol, test_id)
    registry, runner = _runner(
        require_symbol, test_id, managed_root, probe_script
    )
    registration = registry.resolve("probe")
    assert Path(registration.executable).resolve() == Path(sys.executable).resolve()
    assert Path(registration.script_path).resolve() == probe_script.resolve()
    spec = execution_spec.model_validate(execution_spec_payload(entrypoint="probe"))
    dumped_spec = spec.model_dump(mode="json")
    assert "executable" not in dumped_spec
    assert "command" not in dumped_spec
    result = runner.run(spec)
    assert result.status == "succeeded"
    assert result.exit_code == 0
    assert result.process_started is True
    assert result.entrypoint == "probe"


@pytest.mark.parametrize(
    "case_id",
    [
        pytest.param("unregistered-id", id="T05-A-CMD-002-unregistered-id"),
        pytest.param("caller-executable", id="T05-A-CMD-002-caller-executable"),
    ],
)
def test_T05_A_CMD_002_unregistered_or_arbitrary_executable_is_rejected(
    require_symbol: Callable[[str, str, str], Any],
    execution_spec_payload: Callable[..., dict[str, Any]],
    managed_root: Path,
    probe_script: Path,
    case_id: str,
) -> None:
    """T05-A-CMD-002: untrusted executable selection is rejected before spawn."""

    test_id = "T05-A-CMD-002"
    execution_spec, _registry_type, _runner_type = _api(require_symbol, test_id)
    _registry, runner = _runner(
        require_symbol, test_id, managed_root, probe_script
    )
    if case_id == "caller-executable":
        with pytest.raises(ValidationError):
            execution_spec.model_validate(
                execution_spec_payload(executable="untrusted/program")
            )
        return
    spec = execution_spec.model_validate(
        execution_spec_payload(entrypoint="not-registered")
    )
    result = runner.run(spec)
    assert result.status == "rejected"
    assert result.error.code == "entrypoint_not_allowed"
    assert result.process_started is False


def test_T05_A_CMD_003_shell_metacharacters_are_plain_argv(
    require_symbol: Callable[[str, str, str], Any],
    execution_spec_payload: Callable[..., dict[str, Any]],
    managed_root: Path,
    probe_script: Path,
    outside_sentinel: Path,
) -> None:
    """T05-A-CMD-003: shell metacharacters never gain command semantics."""

    test_id = "T05-A-CMD-003"
    arguments = [
        ";",
        "&",
        "|",
        "$()",
        "`",
        ">",
        "<",
        "^",
        "%FAKE_TEST_VALUE%",
        "!FAKE_TEST_VALUE!",
    ]
    before = outside_sentinel.read_bytes()
    result = _run(
        require_symbol,
        test_id,
        execution_spec_payload,
        managed_root,
        probe_script,
        argv=["argv", *arguments],
    )
    assert result.status == "succeeded"
    assert json.loads(result.stdout) == arguments
    assert outside_sentinel.read_bytes() == before


@pytest.mark.parametrize(
    "forbidden_name",
    [
        pytest.param("cmd.exe", id="T05-A-CMD-004-cmd-exe"),
        pytest.param("powershell.exe", id="T05-A-CMD-004-powershell-exe"),
        pytest.param("pwsh", id="T05-A-CMD-004-pwsh"),
        pytest.param("bash", id="T05-A-CMD-004-bash"),
        pytest.param("sh", id="T05-A-CMD-004-sh"),
        pytest.param("launch.bat", id="T05-A-CMD-004-bat"),
        pytest.param("launch.cmd", id="T05-A-CMD-004-cmd"),
        pytest.param("launch.ps1", id="T05-A-CMD-004-ps1"),
    ],
)
def test_T05_A_CMD_004_shell_entrypoints_are_never_registrable(
    require_symbol: Callable[[str, str, str], Any],
    managed_root: Path,
    probe_script: Path,
    tmp_path: Path,
    forbidden_name: str,
) -> None:
    """T05-A-CMD-004: shells and shell-script formats are denied by registry."""

    test_id = "T05-A-CMD-004"
    _execution_spec, registry_type, _runner_type = _api(require_symbol, test_id)
    forbidden = tmp_path / forbidden_name
    forbidden.write_text("not executable test data", encoding="utf-8")
    registry = registry_type()
    with pytest.raises(ValueError, match="entrypoint|shell|python|allowed"):
        registry.register_python(
            "forbidden",
            forbidden,
            entrypoint_class="test",
            allowed_environment=(),
        )


def test_T05_A_CMD_005_unicode_spaces_quotes_and_multiple_args_round_trip(
    require_symbol: Callable[[str, str, str], Any],
    execution_spec_payload: Callable[..., dict[str, Any]],
    managed_root: Path,
    probe_script: Path,
) -> None:
    """T05-A-CMD-005: complex argv items reach the child byte-for-byte."""

    test_id = "T05-A-CMD-005"
    arguments = ["with space", "中文参数", '"double"', "'single'", "final"]
    result = _run(
        require_symbol,
        test_id,
        execution_spec_payload,
        managed_root,
        probe_script,
        argv=["argv", *arguments],
    )
    assert result.status == "succeeded"
    assert json.loads(result.stdout) == arguments


def test_T05_A_RUN_001_utf8_stdout_is_captured_safely(
    require_symbol: Callable[[str, str, str], Any],
    execution_spec_payload: Callable[..., dict[str, Any]],
    managed_root: Path,
    probe_script: Path,
) -> None:
    """T05-A-RUN-001: UTF-8 stdout is decoded with safe replacement semantics."""

    test_id = "T05-A-RUN-001"
    result = _run(
        require_symbol,
        test_id,
        execution_spec_payload,
        managed_root,
        probe_script,
        argv=["output", "--stdout", "中文标准输出"],
    )
    assert result.status == "succeeded"
    assert result.stdout == "中文标准输出"
    assert "\ufffd" not in result.stdout
    invalid_utf8 = _run(
        require_symbol,
        test_id,
        execution_spec_payload,
        managed_root,
        probe_script,
        argv=["output", "--stdout-hex", "fffe61"],
    )
    assert invalid_utf8.status == "succeeded"
    assert invalid_utf8.stdout.endswith("a")
    assert "\ufffd" in invalid_utf8.stdout


def test_T05_A_RUN_002_stderr_remains_separate_from_stdout(
    require_symbol: Callable[[str, str, str], Any],
    execution_spec_payload: Callable[..., dict[str, Any]],
    managed_root: Path,
    probe_script: Path,
) -> None:
    """T05-A-RUN-002: stdout and stderr are retained as separate streams."""

    test_id = "T05-A-RUN-002"
    result = _run(
        require_symbol,
        test_id,
        execution_spec_payload,
        managed_root,
        probe_script,
        argv=[
            "output",
            "--stdout",
            "only-stdout",
            "--stderr",
            "only-stderr",
        ],
    )
    assert result.stdout == "only-stdout"
    assert result.stderr == "only-stderr"
    assert "only-stderr" not in result.stdout
    assert "only-stdout" not in result.stderr


def test_T05_A_RUN_003_output_caps_drain_without_deadlock(
    require_symbol: Callable[[str, str, str], Any],
    execution_spec_payload: Callable[..., dict[str, Any]],
    resource_limit_payload: Callable[..., dict[str, Any]],
    managed_root: Path,
    probe_script: Path,
) -> None:
    """T05-A-RUN-003: retained bytes are capped while both pipes keep draining."""

    test_id = "T05-A-RUN-003"
    unit = "abcdefghij"
    repeat = 2_000
    result = _run(
        require_symbol,
        test_id,
        execution_spec_payload,
        managed_root,
        probe_script,
        argv=[
            "output",
            "--stdout",
            unit,
            "--stderr",
            unit,
            "--repeat",
            str(repeat),
        ],
        resources=resource_limit_payload(
            max_stdout_bytes=128,
            max_stderr_bytes=96,
        ),
    )
    assert result.status == "succeeded"
    assert len(result.stdout.encode("utf-8")) <= 128
    assert len(result.stderr.encode("utf-8")) <= 96
    assert result.stdout_bytes == len(unit.encode("utf-8")) * repeat
    assert result.stderr_bytes == len(unit.encode("utf-8")) * repeat
    assert result.stdout_truncated is True
    assert result.stderr_truncated is True


def test_T05_A_RUN_004_timeout_terminates_and_reaps_direct_child(
    require_symbol: Callable[[str, str, str], Any],
    execution_spec_payload: Callable[..., dict[str, Any]],
    resource_limit_payload: Callable[..., dict[str, Any]],
    managed_root: Path,
    probe_script: Path,
) -> None:
    """T05-A-RUN-004: timeout performs terminate/grace/kill/final wait."""

    test_id = "T05-A-RUN-004"
    result = _run(
        require_symbol,
        test_id,
        execution_spec_payload,
        managed_root,
        probe_script,
        argv=["sleep", "--seconds", "5"],
        resources=resource_limit_payload(timeout_seconds=0.1),
    )
    assert result.status == "timed_out"
    assert result.error.code == "timeout"
    assert result.timed_out is True
    assert result.process_reaped is True
    assert result.process_alive_after_cleanup is False


@pytest.mark.parametrize(
    ("cleanup_policy", "expected_status"),
    [
        pytest.param("delete", "succeeded", id="T05-A-RUN-005-delete"),
        pytest.param("preserve", "preserved", id="T05-A-RUN-005-preserve"),
    ],
)
def test_T05_A_RUN_005_success_records_cleanup_outcome(
    require_symbol: Callable[[str, str, str], Any],
    execution_spec_payload: Callable[..., dict[str, Any]],
    managed_root: Path,
    probe_script: Path,
    cleanup_policy: str,
    expected_status: str,
) -> None:
    """T05-A-RUN-005: successful cleanup is reported, never assumed."""

    test_id = "T05-A-RUN-005"
    before_entries = {path.resolve() for path in managed_root.iterdir()}
    result = _run(
        require_symbol,
        test_id,
        execution_spec_payload,
        managed_root,
        probe_script,
        cleanup_policy=cleanup_policy,
    )
    assert result.status == "succeeded"
    assert result.cleanup_status == expected_status
    after_entries = {path.resolve() for path in managed_root.iterdir()}
    if cleanup_policy == "delete":
        assert after_entries == before_entries
    else:
        preserved_entries = after_entries - before_entries
        assert len(preserved_entries) == 1
        assert all(path.is_dir() for path in preserved_entries)


def test_T05_A_RUN_006_cleanup_failure_cannot_masquerade_as_success(
    require_symbol: Callable[[str, str, str], Any],
    execution_spec_payload: Callable[..., dict[str, Any]],
    managed_root: Path,
    probe_script: Path,
) -> None:
    """T05-A-RUN-006: cleanup failure is structured and blocks actual truth."""

    test_id = "T05-A-RUN-006"

    def fail_cleanup(_workspace: Path) -> None:
        raise OSError("controlled cleanup failure")

    result = _run(
        require_symbol,
        test_id,
        execution_spec_payload,
        managed_root,
        probe_script,
        cleanup=fail_cleanup,
    )
    assert result.status == "failed"
    assert result.cleanup_status == "failed"
    assert result.error.code == "cleanup_failed"
    assert result.actual_execution is False


def test_T05_A_RUN_007_persisted_result_redacts_fake_secrets(
    require_symbol: Callable[[str, str, str], Any],
    execution_spec_payload: Callable[..., dict[str, Any]],
    managed_root: Path,
    probe_script: Path,
) -> None:
    """T05-A-RUN-007: stdout, stderr, errors and URI queries are redacted."""

    test_id = "T05-A-RUN-007"
    fake_secret = "sk-test-not-a-real-secret"
    fake_token = "fake-token-for-redaction-test"
    result = _run(
        require_symbol,
        test_id,
        execution_spec_payload,
        managed_root,
        probe_script,
        allowed_environment=("CALLBACK_URI",),
        argv=[
            "fail",
            "--code",
            "19",
            "--stdout",
            fake_secret,
            "--stderr",
            fake_token,
        ],
        environment={
            "variables": {
                "CALLBACK_URI": f"https://example.invalid/result?token={fake_token}"
            },
            "dependency_allowlist": [],
        },
    )
    serialized = json.dumps(result.model_dump(mode="json"), ensure_ascii=False)
    assert fake_secret not in serialized
    assert fake_token not in serialized
    assert result.status == "failed"


def test_T05_A_RUN_008_child_receives_only_allowlisted_environment(
    require_symbol: Callable[[str, str, str], Any],
    execution_spec_payload: Callable[..., dict[str, Any]],
    managed_root: Path,
    probe_script: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T05-A-RUN-008: parent credentials are not inherited by the child."""

    test_id = "T05-A-RUN-008"
    fake_values = {
        "API_KEY": "sk-test-not-a-real-secret",
        "TOKEN": "fake-token-for-redaction-test",
        "SECRET": "fake-secret-parent-only",
        "PASSWORD": "fake-password-parent-only",
    }
    for name, value in fake_values.items():
        monkeypatch.setenv(name, value)
    result = _run(
        require_symbol,
        test_id,
        execution_spec_payload,
        managed_root,
        probe_script,
        allowed_environment=("SAFE_TEST_VALUE",),
        argv=[
            "env",
            "--name",
            "SAFE_TEST_VALUE",
            "--name",
            "API_KEY",
            "--name",
            "TOKEN",
            "--name",
            "SECRET",
            "--name",
            "PASSWORD",
        ],
        environment={
            "variables": {"SAFE_TEST_VALUE": "visible-to-probe"},
            "dependency_allowlist": [],
        },
    )
    observed = json.loads(result.stdout)
    assert observed["SAFE_TEST_VALUE"] == "visible-to-probe"
    assert all(observed[name] in {None, "", "[REDACTED]"} for name in fake_values)


@pytest.mark.parametrize(
    "mode",
    [
        pytest.param("test", id="T05-A-RUN-009-test"),
        pytest.param("dry_run", id="T05-A-RUN-009-dry-run"),
    ],
)
def test_T05_A_RUN_009_noop_is_never_actual(
    require_symbol: Callable[[str, str, str], Any],
    execution_spec_payload: Callable[..., dict[str, Any]],
    managed_root: Path,
    probe_script: Path,
    mode: str,
) -> None:
    """T05-A-RUN-009: noop may succeed in non-actual modes but is not actual."""

    test_id = "T05-A-RUN-009"
    result = _run(
        require_symbol,
        test_id,
        execution_spec_payload,
        managed_root,
        probe_script,
        mode=mode,
        argv=["noop"],
    )
    assert result.status == "succeeded"
    if mode == "test":
        assert result.exit_code == 0
        assert result.process_started is True
    else:
        assert result.exit_code is None
        assert result.process_started is False
    assert result.actual_execution is False


def test_T05_A_RUN_010_failure_preserves_code_and_sanitized_stderr(
    require_symbol: Callable[[str, str, str], Any],
    execution_spec_payload: Callable[..., dict[str, Any]],
    managed_root: Path,
    probe_script: Path,
) -> None:
    """T05-A-RUN-010: nonzero exit details remain precise and sanitized."""

    test_id = "T05-A-RUN-010"
    fake_secret = "fake-token-for-redaction-test"
    result = _run(
        require_symbol,
        test_id,
        execution_spec_payload,
        managed_root,
        probe_script,
        argv=[
            "fail",
            "--code",
            "23",
            "--stderr",
            f"controlled failure {fake_secret}",
        ],
    )
    assert result.status == "failed"
    assert result.exit_code == 23
    assert result.error.code == "nonzero_exit"
    assert "controlled failure" in result.stderr
    assert fake_secret not in result.stderr
    assert result.actual_execution is False
