"""Wave B 离线 integration harness 的确定性与泄密防护测试。"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "integration" / "fixtures" / "wave_b_offline_fixture.json"


def run_harness(fixture: Path, output: Path) -> subprocess.CompletedProcess[str]:
    """以固定 Python 解释器运行 Wave B 的离线 harness。"""
    return subprocess.run(
        [
            sys.executable,
            "scripts/eval/wave_b_offline_harness.py",
            "--fixture",
            str(fixture),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_offline_harness_is_deterministic_and_planned_only(tmp_path: Path) -> None:
    """相同固定夹具应产生相同 planned 清单，且不伪造评测指标。"""
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    first_run = run_harness(FIXTURE, first)
    second_run = run_harness(FIXTURE, second)
    assert first_run.returncode == 0, first_run.stderr
    assert second_run.returncode == 0, second_run.stderr
    assert first.read_bytes() == second.read_bytes()
    assert first.with_suffix(".csv").read_bytes() == second.with_suffix(".csv").read_bytes()
    payload = json.loads(first.read_text(encoding="utf-8"))
    assert payload["mode"] == "mock"
    assert payload["status"] == "planned"
    assert payload["harness"] == {
        "fixture_id": "wave-b-offline-contract",
        "owner": "T09",
        "purpose": "offline-low-cost-e2e",
    }
    assert [entry["variant"] for entry in payload["variants"]] == [
        "no-RAG",
        "no-reviewer",
        "no-HITL",
        "single-agent",
        "full-system",
    ]
    assert all("score" not in entry and "metrics" not in entry for entry in payload["variants"])
    with first.with_suffix(".csv").open(encoding="utf-8", newline="") as handle:
        assert csv.DictReader(handle).fieldnames == [
            "variant",
            "mode",
            "seed",
            "input_manifest",
            "status",
        ]


def write_fixture(path: Path, **overrides: object) -> None:
    """写入供失败路径测试使用的最小有效离线夹具。"""
    fixture: dict[str, object] = {
        "execution": "offline",
        "fixture_id": "test-fixture",
        "input_manifest": "fixtures/test.json",
        "mode": "mock",
        "owner": "T09",
        "seed": 17,
        "status": "planned",
    }
    fixture.update(overrides)
    path.write_text(json.dumps(fixture), encoding="utf-8")


def test_offline_harness_rejects_all_credential_field_categories(tmp_path: Path) -> None:
    """所有受限凭证字段类别都必须明确失败并定位 T09 owner。"""
    for field in ("api_key", "client_token", "password", "session_cookie", "authorization", "secret_note"):
        unsafe_fixture = tmp_path / f"unsafe-{field}.json"
        write_fixture(unsafe_fixture, **{field: "not-a-real-secret"})
        result = run_harness(unsafe_fixture, tmp_path / f"{field}-output.json")
        assert result.returncode == 2
        assert f"fixture-error:{unsafe_fixture}:owner=T09:forbidden-secret-field:{field}" in result.stderr


def test_offline_harness_rejects_unknown_owner_and_credential_value(tmp_path: Path) -> None:
    """未知 owner 与可输出的疑似凭证值均不可进入 planned 输出。"""
    unknown_owner = tmp_path / "unknown-owner.json"
    write_fixture(unknown_owner, owner="T04")
    unknown_result = run_harness(unknown_owner, tmp_path / "unknown-owner-output.json")
    assert unknown_result.returncode == 2
    assert f"fixture-error:{unknown_owner}:owner=T09:unknown-owner:'T04'" in unknown_result.stderr
    unsafe_value = tmp_path / "unsafe-value.json"
    write_fixture(unsafe_value, input_manifest="Bearer not-a-real-token")
    value_result = run_harness(unsafe_value, tmp_path / "unsafe-value-output.json")
    assert value_result.returncode == 2
    assert f"fixture-error:{unsafe_value}:owner=T09:suspected-credential-value:input_manifest" in value_result.stderr


def test_offline_harness_does_not_overwrite_input_fixture(tmp_path: Path) -> None:
    """输出路径与输入 fixture 相同时必须安全失败且保留原始输入。"""
    fixture = tmp_path / "fixture.json"
    write_fixture(fixture)
    before = fixture.read_bytes()
    result = run_harness(fixture, fixture)
    assert result.returncode == 2
    assert f"fixture-error:{fixture}:owner=T09:output-must-not-overwrite-fixture" in result.stderr
    assert fixture.read_bytes() == before
