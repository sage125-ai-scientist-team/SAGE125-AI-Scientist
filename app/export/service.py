"""Canonical report export orchestration and artifact registration."""

from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.api.artifact_registry import (
    ArtifactNotFound,
    ArtifactRecord,
    SQLiteArtifactRegistry,
)
from app.export.canonical import CanonicalReport, CanonicalReportSource
from app.export.renderers import (
    render_report_json,
    render_report_markdown,
    render_report_pdf,
)


ExportFormat = Literal["json", "markdown", "pdf"]


class CanonicalReportIdentityError(RuntimeError):
    pass


class ExportStorageError(RuntimeError):
    """Safe wrapper for a filesystem failure during atomic export creation."""

    def __init__(self, format_name: ExportFormat, cause: OSError) -> None:
        super().__init__(f"failed to persist {format_name} export")
        self.format_name = format_name
        self.cause = cause


@dataclass(frozen=True)
class ExportResult:
    items: list[ArtifactRecord]
    reused: bool


_FORMAT_METADATA: dict[ExportFormat, tuple[str, str, str]] = {
    "json": ("report.json", "canonical_report_json", "application/json"),
    "markdown": ("report.md", "canonical_report_markdown", "text/markdown"),
    "pdf": ("report.pdf", "canonical_report_pdf", "application/pdf"),
}


class ExportService:
    """Render all formats from one validated report and register immutable files."""

    def __init__(
        self,
        *,
        registry: SQLiteArtifactRegistry,
        source: CanonicalReportSource,
        root: str | Path,
    ) -> None:
        self.registry = registry
        self.source = source
        self.root = Path(root).resolve(strict=False)

    @staticmethod
    def _artifact_id(report: CanonicalReport, format_name: ExportFormat) -> str:
        identity = f"{report.job_id}:{report.content_sha256}:{format_name}"
        suffix = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
        return f"artifact-{suffix}"

    @staticmethod
    def _validate_identity(
        report: CanonicalReport,
        *,
        job_id: str,
        question_id: str,
        run_id: str,
    ) -> None:
        actual = (report.job_id, report.question_id, report.run_id)
        expected = (job_id, question_id, run_id)
        if actual != expected:
            raise CanonicalReportIdentityError(
                "canonical report identity does not match the requested job"
            )

    def _write_atomic(
        self,
        report: CanonicalReport,
        format_name: ExportFormat,
        destination: Path,
    ) -> None:
        temporary: Path | None = None
        descriptor: int | None = None
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            # Stage beneath a short, stable directory.  Putting the temporary file
            # beside ``destination`` repeats the job/content-hash hierarchy and can
            # exceed legacy Windows MAX_PATH in a long checkout or pytest temp root.
            staging_directory = self.root / ".tmp"
            staging_directory.mkdir(parents=True, exist_ok=True)
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{format_name}.",
                suffix=".tmp",
                dir=staging_directory,
            )
            os.close(descriptor)
            descriptor = None
            temporary = Path(temporary_name)
            if format_name == "json":
                temporary.write_bytes(render_report_json(report))
            elif format_name == "markdown":
                temporary.write_bytes(render_report_markdown(report))
            else:
                render_report_pdf(report, temporary)
            os.replace(temporary, destination)
        except OSError as exc:
            raise ExportStorageError(format_name, exc) from None
        finally:
            if descriptor is not None:
                os.close(descriptor)
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def get_report(
        self,
        *,
        job_id: str,
        question_id: str,
        run_id: str,
    ) -> CanonicalReport:
        report = self.source.get_report(
            job_id=job_id,
            question_id=question_id,
            run_id=run_id,
        )
        self._validate_identity(
            report,
            job_id=job_id,
            question_id=question_id,
            run_id=run_id,
        )
        return report

    def export(
        self,
        *,
        job_id: str,
        question_id: str,
        run_id: str,
        actor_id: str,
        idempotency_key: str,
        formats: list[ExportFormat],
    ) -> ExportResult:
        report = self.get_report(
            job_id=job_id,
            question_id=question_id,
            run_id=run_id,
        )
        request_identity = ":".join(
            [job_id, question_id, run_id, report.content_sha256, *sorted(formats)]
        )
        request_hash = hashlib.sha256(request_identity.encode("utf-8")).hexdigest()
        self.registry.claim_export_request(
            actor_id=actor_id,
            idempotency_key=idempotency_key,
            job_id=job_id,
            request_hash=request_hash,
        )
        # ``content_sha256`` already binds job/question/run identity, so a second
        # job-id directory is redundant and consumes scarce Windows path budget.
        directory = self.root / report.content_sha256
        records: list[ArtifactRecord] = []
        all_reused = True
        for format_name in formats:
            name, artifact_type, media_type = _FORMAT_METADATA[format_name]
            destination = directory / name
            artifact_id = self._artifact_id(report, format_name)
            try:
                existing = self.registry.get(artifact_id, actor_id=actor_id)
            except ArtifactNotFound:
                pass
            else:
                self.registry.resolve_for_download(artifact_id, actor_id=actor_id)
                records.append(existing)
                continue

            self._write_atomic(report, format_name, destination)
            record, reused = self.registry.register_file(
                artifact_id=artifact_id,
                job_id=job_id,
                question_id=question_id,
                actor_id=actor_id,
                name=name,
                artifact_type=artifact_type,
                media_type=media_type,
                truth_status=report.truth_status,
                path=destination,
            )
            records.append(record)
            all_reused = all_reused and reused
        return ExportResult(items=records, reused=all_reused)
