"""T09-B-001 的 Ruff 与覆盖率门禁集成测试。"""

from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _run(command: list[str], cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, check=False)


def test_t09_b001_config_and_ci_wiring_are_blocking() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert config["tool"]["ruff"]["target-version"] == "py312"
    assert config["tool"]["ruff"]["lint"]["select"] == ["E4", "E7", "E9", "F"]
    assert config["tool"]["coverage"]["run"]["source"] == ["app"]
    assert config["tool"]["coverage"]["report"]["fail_under"] == 65

    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "python -X utf8 -m ruff check scripts/eval tests/integration" in workflow
    assert "python -X utf8 -m coverage run" in workflow
    assert "--fail-under=65" in workflow
    for bypass in ("continue-on-error", "--exit-zero", "|| true"):
        assert bypass not in workflow


def test_t09_b001_ruff_gate_accepts_clean_code_and_rejects_unused_import(tmp_path: Path) -> None:
    clean_file = tmp_path / "clean.py"
    clean_file.write_text("def value() -> int:\n    return 1\n", encoding="utf-8", newline="\n")
    clean_result = _run([sys.executable, "-m", "ruff", "check", str(clean_file)], ROOT)
    assert clean_result.returncode == 0, clean_result.stderr

    bad_file = tmp_path / "unused_import.py"
    bad_file.write_text("import os\n", encoding="utf-8", newline="\n")
    bad_result = _run([sys.executable, "-m", "ruff", "check", str(bad_file)], ROOT)
    assert bad_result.returncode != 0
    assert "F401" in bad_result.stdout


def test_t09_b001_coverage_gate_accepts_full_coverage(tmp_path: Path) -> None:
    (tmp_path / "covered.py").write_text(
        "def answer() -> int:\n    return 42\n", encoding="utf-8", newline="\n"
    )
    test_file = tmp_path / "test_covered.py"
    test_file.write_text(
        "from covered import answer\n\n\ndef test_answer() -> None:\n    assert answer() == 42\n",
        encoding="utf-8",
        newline="\n",
    )
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(tmp_path)
    data_file = tmp_path / "covered.data"
    run_result = _run(
        [
            sys.executable,
            "-m",
            "coverage",
            "run",
            f"--data-file={data_file}",
            f"--source={tmp_path}",
            "-m",
            "pytest",
            "-q",
            str(test_file),
        ],
        tmp_path,
        environment,
    )
    assert run_result.returncode == 0, run_result.stderr
    report_result = _run(
        [sys.executable, "-m", "coverage", "report", f"--data-file={data_file}", "--fail-under=100"],
        tmp_path,
        environment,
    )
    assert report_result.returncode == 0, report_result.stdout


def test_t09_b001_coverage_gate_rejects_low_coverage(tmp_path: Path) -> None:
    (tmp_path / "partially_covered.py").write_text(
        "def covered() -> int:\n    return 1\n\n\ndef missed() -> int:\n    return 2\n",
        encoding="utf-8",
        newline="\n",
    )
    test_file = tmp_path / "test_partially_covered.py"
    test_file.write_text(
        "from partially_covered import covered\n\n\ndef test_covered() -> None:\n    assert covered() == 1\n",
        encoding="utf-8",
        newline="\n",
    )
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(tmp_path)
    data_file = tmp_path / "partially-covered.data"
    run_result = _run(
        [
            sys.executable,
            "-m",
            "coverage",
            "run",
            f"--data-file={data_file}",
            f"--source={tmp_path}",
            "-m",
            "pytest",
            "-q",
            str(test_file),
        ],
        tmp_path,
        environment,
    )
    assert run_result.returncode == 0, run_result.stderr
    report_result = _run(
        [sys.executable, "-m", "coverage", "report", f"--data-file={data_file}", "--fail-under=100"],
        tmp_path,
        environment,
    )
    assert report_result.returncode != 0
    assert "fail-under" in report_result.stdout
