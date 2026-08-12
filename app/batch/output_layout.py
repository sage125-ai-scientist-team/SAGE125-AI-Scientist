"""Deterministic, question-scoped Wave B output paths."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Final

from app.batch.errors import BatchRunnerError
from app.contracts.batch import REQUIRED_ARTIFACTS


ARTIFACT_MANIFEST_NAME: Final[str] = "artifact_manifest.json"
SAFE_PATH_SEGMENT: Final[re.Pattern[str]] = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]*$"
)
WINDOWS_RESERVED_NAMES: Final[frozenset[str]] = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{number}" for number in range(1, 10)}
    | {f"LPT{number}" for number in range(1, 10)}
)


@dataclass(frozen=True, slots=True)
class QuestionOutputPaths:
    """The fixed filesystem tree owned by exactly one question."""

    batch_root: Path
    question_id: str
    question_root: Path
    report_pdf: Path
    report_md: Path
    result_json: Path
    evidence_cards_json: Path
    agent_trace_json: Path
    artifact_manifest_json: Path

    def path_for(self, artifact_name: str) -> Path:
        mapping = {
            "report.pdf": self.report_pdf,
            "report.md": self.report_md,
            "result.json": self.result_json,
            "evidence_cards.json": self.evidence_cards_json,
            "agent_trace.json": self.agent_trace_json,
            ARTIFACT_MANIFEST_NAME: self.artifact_manifest_json,
        }
        try:
            return mapping[artifact_name]
        except KeyError as exc:
            raise BatchRunnerError(
                "OUTPUT_PATH_INVALID",
                f"Unknown question artifact: {artifact_name}",
            ) from exc


def validate_question_id_for_path(question_id: str) -> str:
    """Return a safe single path segment or fail closed."""

    if not isinstance(question_id, str) or not question_id:
        raise BatchRunnerError(
            "OUTPUT_PATH_INVALID",
            "question_id must be a non-empty string",
        )
    if question_id != question_id.strip():
        raise BatchRunnerError(
            "OUTPUT_PATH_INVALID",
            "question_id cannot contain leading or trailing whitespace",
        )
    if (
        PurePosixPath(question_id).is_absolute()
        or PureWindowsPath(question_id).is_absolute()
        or "/" in question_id
        or "\\" in question_id
        or question_id in {".", ".."}
        or question_id.endswith((".", " "))
        or not SAFE_PATH_SEGMENT.fullmatch(question_id)
    ):
        raise BatchRunnerError(
            "OUTPUT_PATH_INVALID",
            "question_id must be one safe relative path segment",
        )
    if question_id.split(".", 1)[0].upper() in WINDOWS_RESERVED_NAMES:
        raise BatchRunnerError(
            "OUTPUT_PATH_INVALID",
            f"Windows reserved name is forbidden: {question_id}",
        )
    return question_id


def build_question_output_paths(
    batch_root: str | Path,
    question_id: str,
) -> QuestionOutputPaths:
    """Build the fixed tree without creating files or random identifiers."""

    root = _require_batch_root(batch_root)
    owner = validate_question_id_for_path(question_id)
    question_root = root / owner
    return QuestionOutputPaths(
        batch_root=root,
        question_id=owner,
        question_root=question_root,
        report_pdf=question_root / "report.pdf",
        report_md=question_root / "report.md",
        result_json=question_root / "result.json",
        evidence_cards_json=question_root / "evidence_cards.json",
        agent_trace_json=question_root / "agent_trace.json",
        artifact_manifest_json=question_root / ARTIFACT_MANIFEST_NAME,
    )


def validate_output_path_boundary(
    batch_root: str | Path,
    question_id: str,
    relative_path: str | Path,
) -> Path:
    """Resolve one relative path only inside its owning question directory."""

    root = _require_batch_root(batch_root)
    owner = validate_question_id_for_path(question_id)
    try:
        raw = os.fspath(relative_path)
    except TypeError as exc:
        raise BatchRunnerError(
            "OUTPUT_PATH_INVALID",
            "output path must be path-like",
        ) from exc
    if not isinstance(raw, str) or not raw:
        raise BatchRunnerError(
            "OUTPUT_PATH_INVALID",
            "output path must be a non-empty relative path",
        )
    if PurePosixPath(raw).is_absolute() or PureWindowsPath(raw).is_absolute():
        raise BatchRunnerError(
            "OUTPUT_PATH_INVALID",
            "absolute output paths are forbidden",
        )
    normalized = raw.replace("\\", "/")
    parts = PurePosixPath(normalized).parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise BatchRunnerError(
            "OUTPUT_PATH_INVALID",
            "output path traversal is forbidden",
        )
    if parts[0] != owner:
        raise BatchRunnerError(
            "OUTPUT_PATH_INVALID",
            f"output path is not owned by question_id={owner}",
        )

    root_absolute = Path(os.path.abspath(root))
    question_absolute = root_absolute / owner
    target_absolute = root_absolute.joinpath(*parts)
    if not _is_within(target_absolute, question_absolute):
        raise BatchRunnerError(
            "OUTPUT_PATH_INVALID",
            "output path escapes its question directory",
        )
    _reject_symlink_chain(root_absolute, target_absolute)
    resolved_root = root_absolute.resolve(strict=False)
    resolved_target = target_absolute.resolve(strict=False)
    if not _is_within(resolved_target, resolved_root):
        raise BatchRunnerError(
            "OUTPUT_PATH_INVALID",
            "resolved output path escapes the batch root",
        )
    return root.joinpath(*parts)


def create_question_output_directory(
    paths: QuestionOutputPaths,
    *,
    expected_question_id: str | None = None,
) -> Path:
    """Create one question directory while preserving retry ownership."""

    if not isinstance(paths, QuestionOutputPaths):
        raise TypeError("paths must be QuestionOutputPaths")
    if expected_question_id is not None:
        expected = validate_question_id_for_path(expected_question_id)
        if paths.question_id != expected:
            raise BatchRunnerError(
                "OUTPUT_PATH_INVALID",
                "retry attempted to write another question directory",
            )
    canonical = build_question_output_paths(paths.batch_root, paths.question_id)
    if paths != canonical:
        raise BatchRunnerError(
            "OUTPUT_PATH_INVALID",
            "QuestionOutputPaths does not match deterministic derivation",
        )
    paths.batch_root.mkdir(parents=True, exist_ok=True)
    target = validate_output_path_boundary(
        paths.batch_root,
        paths.question_id,
        paths.question_id,
    )
    target.mkdir(parents=False, exist_ok=True)
    _reject_symlink_chain(
        Path(os.path.abspath(paths.batch_root)),
        Path(os.path.abspath(target)),
    )
    if not target.is_dir():
        raise BatchRunnerError(
            "OUTPUT_PATH_INVALID",
            "question output target is not a directory",
        )
    return target


def list_required_artifact_paths(
    paths: QuestionOutputPaths,
) -> tuple[Path, ...]:
    """List exactly the five artifacts frozen by the Wave A contract."""

    if not isinstance(paths, QuestionOutputPaths):
        raise TypeError("paths must be QuestionOutputPaths")
    return tuple(paths.path_for(name) for name in REQUIRED_ARTIFACTS)


def _require_batch_root(batch_root: str | Path) -> Path:
    try:
        raw = os.fspath(batch_root)
    except TypeError as exc:
        raise BatchRunnerError(
            "OUTPUT_PATH_INVALID",
            "batch_root must be path-like",
        ) from exc
    if not isinstance(raw, str) or not raw.strip():
        raise BatchRunnerError(
            "OUTPUT_PATH_INVALID",
            "batch_root must be a non-empty path",
        )
    return Path(raw)


def _is_within(candidate: Path, parent: Path) -> bool:
    try:
        return os.path.commonpath((candidate, parent)) == os.path.commonpath(
            (parent, parent)
        )
    except ValueError:
        return False


def _reject_symlink_chain(root: Path, target: Path) -> None:
    if root.is_symlink():
        raise BatchRunnerError(
            "ARTIFACT_SYMLINK_REJECTED",
            f"Symlink output component rejected: {root}",
        )
    try:
        relative = target.relative_to(root)
    except ValueError as exc:
        raise BatchRunnerError(
            "OUTPUT_PATH_INVALID",
            "output path is outside the batch root",
        ) from exc
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise BatchRunnerError(
                "ARTIFACT_SYMLINK_REJECTED",
                f"Symlink output component rejected: {current}",
            )
