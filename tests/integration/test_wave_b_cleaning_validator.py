"""Wave B cleaning validator：只读发布候选污染检查的 integration 测试。"""

from __future__ import annotations

import hashlib
import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "eval" / "wave_b_cleaning_validator.py"
EVAL_ROOT = ROOT / "scripts" / "eval"
if str(EVAL_ROOT) not in sys.path:
    sys.path.insert(0, str(EVAL_ROOT))

cleaning_validator = importlib.import_module("wave_b_cleaning_validator")


def write_json(path: Path, payload: object) -> None:
    """写入合成测试 JSON，不含真实评测或凭证。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def make_candidate(tmp_path: Path, files: dict[str, object] | None = None) -> Path:
    """创建最小 completed 候选目录及显式 artifact inventory。"""
    candidate = tmp_path / "candidate"
    candidate.mkdir(parents=True)
    artifacts = files or {"result.json": {"mode": "real", "status": "completed"}}
    for relative, payload in artifacts.items():
        path = candidate / relative
        if isinstance(payload, bytes):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        elif isinstance(payload, str):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(payload, encoding="utf-8")
        else:
            write_json(path, payload)
    write_json(candidate / "release.json", {"files": sorted(artifacts), "status": "completed"})
    return candidate


def run_validator(candidate: Path, manifest: str = "release.json") -> subprocess.CompletedProcess[str]:
    """在仓库根目录执行只读 CLI。"""
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--candidate", str(candidate), "--manifest", manifest],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def tree_hashes(root: Path) -> dict[str, str]:
    """以相对路径和 SHA-256 记录输入树，验证 validator 不改动输入。"""
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and not path.is_symlink()
    }


def report(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    """解析 validator 的稳定 JSON 标准输出。"""
    return json.loads(result.stdout)


def rules(result: subprocess.CompletedProcess[str]) -> list[str]:
    """提取失败规则，便于断言结构化定位。"""
    return [item["rule"] for item in report(result)["failures"]]


def test_clean_candidate_passes_is_deterministic_and_read_only(tmp_path: Path) -> None:
    """合法 mock 文本、普通 token/cookie 字样不应脱离结构误报。"""
    candidate = make_candidate(
        tmp_path,
        {
            "notes.md": "fixture documentation mentions mock, planned, failed, token, cookie, and authorization as ordinary words.",
            "result.json": {"mode": "real", "note": "token cookie ordinary text", "status": "completed"},
        },
    )
    before = tree_hashes(candidate)
    first = run_validator(candidate)
    second = run_validator(candidate)
    assert first.returncode == 0, first.stdout
    assert second.returncode == 0, second.stdout
    assert first.stdout.encode("utf-8") == second.stdout.encode("utf-8")
    assert first.stderr == second.stderr == ""
    assert report(first) == {"check": "wave_b_cleaning", "failures": [], "owner": "T09", "passed": True}
    assert str(candidate) not in first.stdout
    assert tree_hashes(candidate) == before


def test_utf8_bom_json_artifacts_are_accepted(tmp_path: Path) -> None:
    """Windows 工具常见的 UTF-8 BOM 不应使结构化候选误判为非法 JSON。"""
    candidate = make_candidate(tmp_path)
    for name, payload in (
        ("release.json", {"files": ["result.json"], "status": "completed"}),
        ("result.json", {"mode": "real", "status": "completed"}),
    ):
        (candidate / name).write_bytes(b"\xef\xbb\xbf" + json.dumps(payload).encode("utf-8"))
    result = run_validator(candidate)
    assert result.returncode == 0, result.stdout
    assert report(result)["passed"] is True


@pytest.mark.parametrize(
    ("relative", "expected_rule"),
    [
        (".pytest_tmp/marker.txt", "temporary-directory"),
        (".pytest_cache/marker.txt", "temporary-directory"),
        ("gov-tests/content-review.json", "temporary-directory"),
        ("pytest-basetemp/marker.txt", "temporary-directory"),
        ("__pycache__/module.pyc", "temporary-directory"),
        ("compiled.pyc", "compiled-python"),
    ],
)
def test_temporary_artifacts_are_rejected(tmp_path: Path, relative: str, expected_rule: str) -> None:
    """候选发布目录不得包含测试缓存、治理临时物或编译产物。"""
    candidate = make_candidate(tmp_path)
    marker = candidate / relative
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("synthetic test temporary artifact", encoding="utf-8")
    result = run_validator(candidate)
    assert result.returncode == 1
    assert expected_rule in rules(result)


@pytest.mark.parametrize(
    "status",
    ["planned", "failed", "partial", "incomplete", "error", "aborted", "cancelled", "rejected"],
)
def test_non_release_result_statuses_are_rejected(tmp_path: Path, status: str) -> None:
    """计划、失败或未完成结构化 export 不得被 manifest 伪装为 completed。"""
    candidate = make_candidate(tmp_path, {"result.json": {"mode": "real", "status": status}})
    result = run_validator(candidate)
    assert result.returncode == 1
    assert "non-release-status" in rules(result)
    assert report(result)["failures"][0]["path"] == "result.json"


def test_non_string_result_status_is_rejected(tmp_path: Path) -> None:
    """结构化 artifact 的 status 不是 JSON 字符串时必须明确失败。"""
    candidate = make_candidate(tmp_path, {"result.json": {"mode": "real", "status": True}})
    result = run_validator(candidate)
    assert result.returncode == 1
    assert "invalid-status-type" in rules(result)


@pytest.mark.parametrize(
    "payload",
    [
        {"mode": "mock", "status": "completed"},
        {"mock_mode": True, "status": "completed"},
    ],
)
def test_mock_result_is_rejected(tmp_path: Path, payload: dict[str, object]) -> None:
    """结构化 mode=mock 和 JSON 布尔 mock_mode=true 都不能进入候选集合。"""
    candidate = make_candidate(tmp_path, {"result.json": payload})
    result = run_validator(candidate)
    assert result.returncode == 1
    assert "mock-result" in rules(result)


def test_mock_mode_string_is_not_treated_as_boolean_marker(tmp_path: Path) -> None:
    """只有 JSON 真布尔值才表示 mock_mode 污染，普通文本不触发误报。"""
    candidate = make_candidate(tmp_path, {"result.json": {"mock_mode": "true", "status": "completed"}})
    result = run_validator(candidate)
    assert result.returncode == 0, result.stdout


def test_missing_invalid_and_inconsistent_manifests_fail(tmp_path: Path) -> None:
    """manifest 缺失、非法 JSON、路径逃逸和清单不一致必须明确失败。"""
    missing = tmp_path / "missing"
    missing.mkdir()
    missing_result = run_validator(missing)
    assert missing_result.returncode == 1
    assert "manifest-missing" in rules(missing_result)
    invalid = tmp_path / "invalid"
    invalid.mkdir()
    (invalid / "release.json").write_text("{", encoding="utf-8")
    invalid_result = run_validator(invalid)
    assert invalid_result.returncode == 1
    assert "manifest-invalid-json" in rules(invalid_result)
    inconsistent = make_candidate(tmp_path / "inconsistent")
    write_json(inconsistent / "release.json", {"files": ["../outside.json"], "status": "completed"})
    inconsistent_result = run_validator(inconsistent)
    assert inconsistent_result.returncode == 1
    assert "manifest-invalid-path" in rules(inconsistent_result)
    windows_path = make_candidate(tmp_path / "windows-path")
    windows_path_result = run_validator(windows_path, r"C:\\outside.json")
    assert windows_path_result.returncode == 1
    assert "manifest-invalid-path" in rules(windows_path_result)
    missing_artifact = make_candidate(tmp_path / "missing-artifact")
    write_json(missing_artifact / "release.json", {"files": ["not-present.json"], "status": "completed"})
    missing_artifact_result = run_validator(missing_artifact)
    assert missing_artifact_result.returncode == 1
    assert "manifest-missing-artifact" in rules(missing_artifact_result)
    invalid_status = make_candidate(tmp_path / "invalid-status")
    write_json(invalid_status / "release.json", {"files": ["result.json"], "status": True})
    invalid_status_result = run_validator(invalid_status)
    assert invalid_status_result.returncode == 1
    assert "manifest-not-completed" in rules(invalid_status_result)
    invalid_files = make_candidate(tmp_path / "invalid-files")
    write_json(invalid_files / "release.json", {"files": "result.json", "status": "completed"})
    invalid_files_result = run_validator(invalid_files)
    assert invalid_files_result.returncode == 1
    assert "manifest-invalid-files" in rules(invalid_files_result)
    unlisted = make_candidate(tmp_path / "unlisted")
    write_json(unlisted / "extra.json", {"mode": "real", "status": "completed"})
    unlisted_result = run_validator(unlisted)
    assert unlisted_result.returncode == 1
    assert "manifest-unlisted-artifact" in rules(unlisted_result)


def test_missing_candidate_and_multiple_failures_are_stably_sorted(tmp_path: Path) -> None:
    """不存在候选和多个污染项均应完整、稳定地返回，而非只报告第一项。"""
    missing_result = run_validator(tmp_path / "does-not-exist")
    assert missing_result.returncode == 1
    assert rules(missing_result) == ["candidate-missing"]
    candidate = make_candidate(tmp_path / "multiple", {"bad.json": {"mode": "mock", "status": "failed"}})
    (candidate / ".pytest_tmp").mkdir()
    first = run_validator(candidate)
    second = run_validator(candidate)
    assert first.returncode == second.returncode == 1
    assert first.stdout == second.stdout
    failures = report(first)["failures"]
    assert len(failures) >= 3
    assert failures == sorted(failures, key=lambda item: (item["rule"], item["path"], item["reason"]))


def test_symlink_is_rejected_without_following_outside_candidate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """模拟链接项必须被定位并拒绝，扫描器不能将其作为普通文件读取。"""
    candidate = make_candidate(tmp_path)
    link = candidate / "linked.json"
    write_json(link, {"mode": "real", "status": "completed"})
    original_is_symlink = Path.is_symlink

    def simulated_is_symlink(path: Path) -> bool:
        return path == link or original_is_symlink(path)

    monkeypatch.setattr(Path, "is_symlink", simulated_is_symlink)
    result = cleaning_validator.validate(candidate, Path("release.json"))
    assert result["passed"] is False
    assert any(item["rule"] == "symlink" and item["path"] == "linked.json" for item in result["failures"])
