"""Wave B 发布候选清理校验器：只读检查候选目录与显式清单。"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any


OWNER = "T09"
REJECTED_STATUSES = frozenset(
    {"aborted", "cancelled", "error", "failed", "incomplete", "partial", "planned", "rejected"}
)
TEMPORARY_DIRECTORY_NAMES = frozenset({".pytest_cache", ".pytest_tmp", "__pycache__", "gov-tests"})


def failure(rule: str, path: str, reason: str) -> dict[str, str]:
    """构造具有稳定字段顺序的污染定位记录。"""
    return {"owner": OWNER, "path": path, "reason": reason, "rule": rule}


def relative_path(path: Path, root: Path) -> str:
    """返回稳定的 POSIX 相对路径，不将本机绝对路径写入报告。"""
    return path.relative_to(root).as_posix()


def parse_relative_path(value: object) -> PurePosixPath | None:
    """只接受不逃逸候选目录的非空 POSIX 相对路径。"""
    if not isinstance(value, str) or not value:
        return None
    candidate = PurePosixPath(value.replace("\\", "/"))
    windows_path = PureWindowsPath(value)
    if (
        candidate.is_absolute()
        or windows_path.is_absolute()
        or windows_path.drive
        or "." in candidate.parts
        or ".." in candidate.parts
    ):
        return None
    return candidate


def load_manifest(candidate: Path, manifest_relative: PurePosixPath) -> tuple[set[str], list[dict[str, str]]]:
    """读取候选清单，并返回允许的文件集合和结构化失败。"""
    failures: list[dict[str, str]] = []
    manifest = candidate.joinpath(*manifest_relative.parts)
    manifest_path = manifest_relative.as_posix()
    if not manifest.exists():
        return set(), [failure("manifest-missing", manifest_path, "manifest file does not exist")]
    if manifest.is_symlink():
        return set(), [failure("symlink", manifest_path, "manifest must not be a symlink")]
    if not manifest.is_file():
        return set(), [failure("manifest-not-file", manifest_path, "manifest must be a regular file")]
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        return set(), [failure("manifest-invalid-json", manifest_path, f"line={exc.lineno}:column={exc.colno}")]
    if not isinstance(payload, dict):
        return set(), [failure("manifest-invalid-shape", manifest_path, "root must be an object")]
    status = payload.get("status")
    if not isinstance(status, str) or status != "completed":
        failures.append(failure("manifest-not-completed", manifest_path, "status must be the string completed"))
    values = payload.get("files")
    if not isinstance(values, list):
        failures.append(failure("manifest-invalid-files", manifest_path, "files must be a list"))
        return set(), failures
    listed: set[str] = set()
    for value in values:
        artifact = parse_relative_path(value)
        if artifact is None:
            failures.append(failure("manifest-invalid-path", manifest_path, f"invalid file entry {value!r}"))
            continue
        artifact_path = artifact.as_posix()
        if artifact_path == manifest_path:
            failures.append(failure("manifest-self-reference", manifest_path, "manifest must not list itself"))
            continue
        if artifact_path in listed:
            failures.append(failure("manifest-duplicate-entry", manifest_path, artifact_path))
            continue
        listed.add(artifact_path)
        target = candidate.joinpath(*artifact.parts)
        if not target.exists():
            failures.append(failure("manifest-missing-artifact", artifact_path, "listed artifact does not exist"))
        elif target.is_symlink():
            failures.append(failure("symlink", artifact_path, "listed artifact must not be a symlink"))
        elif not target.is_file():
            failures.append(failure("manifest-artifact-not-file", artifact_path, "listed artifact must be a file"))
    return listed, failures


def scan_candidate(candidate: Path, manifest_relative: PurePosixPath) -> list[dict[str, str]]:
    """扫描候选发布目录，拒绝缓存、符号链接和结构化非发布状态。"""
    listed, failures = load_manifest(candidate, manifest_relative)
    actual_files: set[str] = set()
    for directory, directories, files in os.walk(candidate, followlinks=False):
        current = Path(directory)
        safe_directories: list[str] = []
        for name in sorted(directories):
            child = current / name
            child_path = relative_path(child, candidate)
            if child.is_symlink():
                failures.append(failure("symlink", child_path, "directory symlink is not allowed"))
            elif name in TEMPORARY_DIRECTORY_NAMES or name.startswith(("pytest-", "pytest_")):
                failures.append(failure("temporary-directory", child_path, "test cache or temporary directory"))
            else:
                safe_directories.append(name)
        directories[:] = safe_directories
        for name in sorted(files):
            artifact = current / name
            artifact_path = relative_path(artifact, candidate)
            if artifact.is_symlink():
                failures.append(failure("symlink", artifact_path, "file symlink is not allowed"))
                continue
            actual_files.add(artifact_path)
            if artifact.suffix.lower() == ".pyc":
                failures.append(failure("compiled-python", artifact_path, "compiled Python artifact"))
            if artifact.suffix.lower() != ".json":
                continue
            try:
                payload: Any = json.loads(artifact.read_text(encoding="utf-8-sig"))
            except json.JSONDecodeError as exc:
                failures.append(failure("invalid-json-export", artifact_path, f"line={exc.lineno}:column={exc.colno}"))
                continue
            if not isinstance(payload, dict):
                continue
            status = payload.get("status")
            if "status" in payload and not isinstance(status, str):
                failures.append(failure("invalid-status-type", artifact_path, "status must be a string"))
            elif isinstance(status, str) and status.lower() in REJECTED_STATUSES:
                failures.append(failure("non-release-status", artifact_path, status.lower()))
            mode = payload.get("mode")
            if isinstance(mode, str) and mode.lower() == "mock":
                failures.append(failure("mock-result", artifact_path, "mode=mock"))
            if payload.get("mock_mode") is True:
                failures.append(failure("mock-result", artifact_path, "mock_mode=true"))
    manifest_path = manifest_relative.as_posix()
    artifacts_on_disk = actual_files - {manifest_path}
    for artifact_path in sorted(artifacts_on_disk - listed):
        failures.append(failure("manifest-unlisted-artifact", artifact_path, "artifact is absent from manifest files"))
    return sorted(failures, key=lambda item: (item["rule"], item["path"], item["reason"]))


def validate(candidate_argument: Path, manifest_argument: Path) -> dict[str, object]:
    """执行只读校验并返回稳定 JSON 报告。"""
    if not candidate_argument.exists():
        failures = [failure("candidate-missing", ".", "candidate directory does not exist")]
    elif candidate_argument.is_symlink():
        failures = [failure("symlink", ".", "candidate directory must not be a symlink")]
    elif not candidate_argument.is_dir():
        failures = [failure("candidate-not-directory", ".", "candidate must be a directory")]
    else:
        manifest_relative = parse_relative_path(manifest_argument.as_posix())
        if manifest_relative is None:
            failures = [failure("manifest-invalid-path", ".", "manifest must be a relative path inside candidate")]
        else:
            failures = scan_candidate(candidate_argument.resolve(), manifest_relative)
    return {"check": "wave_b_cleaning", "failures": failures, "owner": OWNER, "passed": not failures}


def main() -> int:
    """从仓库根目录检查候选发布目录；0=干净，1=污染或无效输入。"""
    parser = argparse.ArgumentParser(
        description="Read-only Wave B release-candidate cleaning validator (0=clean, 1=invalid or contaminated)."
    )
    parser.add_argument("--candidate", type=Path, required=True, help="candidate release directory")
    parser.add_argument("--manifest", type=Path, required=True, help="candidate-relative JSON inventory manifest")
    args = parser.parse_args()
    report = validate(args.candidate, args.manifest)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
