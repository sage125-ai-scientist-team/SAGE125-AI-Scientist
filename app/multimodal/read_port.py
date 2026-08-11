"""
T06 production read port for T08 (and other consumers).

Provides durable, identity-bound multimodal artifact storage and listing.
Process-local MultimodalQueue is NOT a production truth source.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from app.contracts.multimodal import BoundingBox, MultimodalArtifact, ValidationStatus
from app.multimodal.errors import ExtractionError

CoordinateSpace = Literal["pdf_user_space", "image_pixel", "csv_placeholder", "unknown"]

# Confidence gate owned by T06: consumers must display status from artifact,
# not invent their own threshold. Exposed for documentation/tests only.
T06_LOW_CONFIDENCE_THRESHOLD = 0.70

_IDENTITY_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


class MultimodalPortError(ExtractionError):
    """Owner-owned read/write port error with stable category for T08 mapping."""

    def __init__(self, category: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.category = category
        self.retryable = retryable


@dataclass(frozen=True)
class PublicSourceRef:
    """Safe source projection — never exposes absolute filesystem paths."""

    source_id: str
    source_label: str
    preview_artifact_id: str
    coordinate_space: CoordinateSpace
    page: int
    bbox: BoundingBox | None


@dataclass(frozen=True)
class MultimodalDetailView:
    """
    Owner-owned detail DTO for T08 panels.

    Keeps bbox/axes/legend/units/confidence/validation_status and a controlled
    source projection. Includes structured data (same as MultimodalArtifact.data).
    """

    run_id: str
    question_id: str
    version_id: str
    artifact: MultimodalArtifact
    public_source: PublicSourceRef
    needs_human_review: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "question_id": self.question_id,
            "version_id": self.version_id,
            "artifact": self.artifact.model_dump(mode="json"),
            "public_source": {
                "source_id": self.public_source.source_id,
                "source_label": self.public_source.source_label,
                "preview_artifact_id": self.public_source.preview_artifact_id,
                "coordinate_space": self.public_source.coordinate_space,
                "page": self.public_source.page,
                "bbox": (
                    None
                    if self.public_source.bbox is None
                    else self.public_source.bbox.model_dump(mode="json")
                ),
            },
            "needs_human_review": self.needs_human_review,
            "low_confidence_threshold": T06_LOW_CONFIDENCE_THRESHOLD,
            "schema_version": "t06.multimodal_detail.v1",
        }


def _validate_identity_token(name: str, value: str) -> str:
    token = (value or "").strip()
    if not token or not _IDENTITY_RE.fullmatch(token):
        raise MultimodalPortError(
            "invalid_contract",
            f"invalid {name}: must be 1..128 of [A-Za-z0-9._:-]",
            retryable=False,
        )
    return token


def _default_store_root() -> Path:
    override = os.environ.get("T06_MULTIMODAL_STORE_DIR", "").strip()
    if override:
        return Path(override)
    # Repo-relative durable default (survives process restart; not process memory).
    return Path(__file__).resolve().parents[2] / "exports" / "multimodal_store"


def _safe_segment(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]


def _identity_dir(root: Path, run_id: str, question_id: str, version_id: str) -> Path:
    return root / _safe_segment(run_id) / _safe_segment(question_id) / _safe_segment(version_id)


def _coordinate_space(artifact: MultimodalArtifact) -> CoordinateSpace:
    st = artifact.provenance.source_type
    if st == "pdf":
        return "pdf_user_space"
    if st in {"csv", "synthetic_fixture", "real_fixture"}:
        # CSV / packet fixtures may use placeholder geometry.
        if any("csv_no_page_bbox" in x for x in artifact.legend):
            return "csv_placeholder"
        if artifact.modality == "chart" and st != "pdf":
            return "image_pixel"
        return "csv_placeholder" if st == "csv" else "unknown"
    if st == "user_upload" and artifact.modality == "chart":
        return "image_pixel"
    return "unknown"


def _sanitize_source_path(raw: str, *, source_id: str) -> str:
    """Replace absolute/local paths with a stable public locator string."""
    name = Path(raw.split("#", 1)[0]).name or "source"
    suffix = ""
    if "#sha256=" in raw:
        suffix = "#" + raw.split("#", 1)[1]
    elif "#" in raw:
        suffix = "#" + raw.split("#", 1)[1]
    return f"t06-source:{source_id[:12]}/{name}{suffix}"


def build_public_source(artifact: MultimodalArtifact) -> PublicSourceRef:
    raw = artifact.provenance.source_path
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    source_id = f"sha256:{digest}"
    label_name = Path(raw.split("#", 1)[0]).name or "source"
    source_label = f"{label_name}#page={artifact.provenance.page}"
    return PublicSourceRef(
        source_id=source_id,
        source_label=source_label,
        preview_artifact_id=artifact.artifact_id,
        coordinate_space=_coordinate_space(artifact),
        page=artifact.provenance.page,
        bbox=artifact.provenance.bbox,
    )


def _public_artifact(artifact: MultimodalArtifact) -> MultimodalArtifact:
    """Return artifact copy with filesystem paths redacted for external consumers."""
    pub = build_public_source(artifact)
    payload = artifact.model_dump(mode="python")
    payload["provenance"] = {
        **payload["provenance"],
        "source_path": _sanitize_source_path(
            artifact.provenance.source_path, source_id=pub.source_id
        ),
    }
    return MultimodalArtifact.model_validate(payload)


def _needs_human_review(artifact: MultimodalArtifact) -> bool:
    if artifact.validation_status in {"needs_review", "failed", "pending"}:
        return True
    return artifact.confidence < T06_LOW_CONFIDENCE_THRESHOLD


class MultimodalArtifactStore:
    """File-backed durable store keyed by run/question/version."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or _default_store_root()).resolve()

    def put_artifact(
        self,
        *,
        run_id: str,
        question_id: str,
        version_id: str,
        artifact: MultimodalArtifact,
    ) -> MultimodalDetailView:
        run_id = _validate_identity_token("run_id", run_id)
        question_id = _validate_identity_token("question_id", question_id)
        version_id = _validate_identity_token("version_id", version_id)
        if not isinstance(artifact, MultimodalArtifact):
            raise MultimodalPortError(
                "invalid_contract", "artifact must be MultimodalArtifact", retryable=False
            )

        folder = _identity_dir(self.root, run_id, question_id, version_id)
        folder.mkdir(parents=True, exist_ok=True)
        public_source = build_public_source(artifact)
        envelope = {
            "schema_version": "t06.multimodal_store.v1",
            "run_id": run_id,
            "question_id": question_id,
            "version_id": version_id,
            "artifact": artifact.model_dump(mode="json"),
            "public_source": {
                "source_id": public_source.source_id,
                "source_label": public_source.source_label,
                "preview_artifact_id": public_source.preview_artifact_id,
                "coordinate_space": public_source.coordinate_space,
                "page": public_source.page,
                "bbox": (
                    None
                    if public_source.bbox is None
                    else public_source.bbox.model_dump(mode="json")
                ),
            },
        }
        path = folder / f"{_safe_segment(artifact.artifact_id)}.json"
        path.write_text(json.dumps(envelope, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return MultimodalDetailView(
            run_id=run_id,
            question_id=question_id,
            version_id=version_id,
            artifact=_public_artifact(artifact),
            public_source=public_source,
            needs_human_review=_needs_human_review(artifact),
        )

    def list_details(
        self,
        *,
        run_id: str,
        question_id: str,
        version_id: str,
    ) -> list[MultimodalDetailView]:
        run_id = _validate_identity_token("run_id", run_id)
        question_id = _validate_identity_token("question_id", question_id)
        version_id = _validate_identity_token("version_id", version_id)
        folder = _identity_dir(self.root, run_id, question_id, version_id)
        if not folder.is_dir():
            return []

        views: list[MultimodalDetailView] = []
        for path in sorted(folder.glob("*.json")):
            try:
                envelope = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise MultimodalPortError(
                    "unavailable",
                    f"corrupt multimodal store entry {path.name}: {exc}",
                    retryable=False,
                ) from exc
            if (
                envelope.get("run_id") != run_id
                or envelope.get("question_id") != question_id
                or envelope.get("version_id") != version_id
            ):
                raise MultimodalPortError(
                    "identity_mismatch",
                    "stored identity does not match requested run/question/version",
                    retryable=False,
                )
            artifact = MultimodalArtifact.model_validate(envelope["artifact"])
            public_source = build_public_source(artifact)
            views.append(
                MultimodalDetailView(
                    run_id=run_id,
                    question_id=question_id,
                    version_id=version_id,
                    artifact=_public_artifact(artifact),
                    public_source=public_source,
                    needs_human_review=_needs_human_review(artifact),
                )
            )
        return views


_DEFAULT_STORE: MultimodalArtifactStore | None = None


def get_default_store() -> MultimodalArtifactStore:
    global _DEFAULT_STORE
    if _DEFAULT_STORE is None:
        _DEFAULT_STORE = MultimodalArtifactStore()
    return _DEFAULT_STORE


def put_multimodal_artifact(
    *,
    run_id: str,
    question_id: str,
    version_id: str,
    artifact: MultimodalArtifact,
    store: MultimodalArtifactStore | None = None,
) -> MultimodalDetailView:
    """Persist an owner-owned multimodal artifact under identity keys."""
    return (store or get_default_store()).put_artifact(
        run_id=run_id,
        question_id=question_id,
        version_id=version_id,
        artifact=artifact,
    )


def list_multimodal_artifacts(
    *,
    run_id: str,
    question_id: str,
    version_id: str,
    store: MultimodalArtifactStore | None = None,
) -> list[MultimodalArtifact]:
    """
    Production read port requested by T08 Wave B owner confirmation.

    Returns sanitized MultimodalArtifact list (paths redacted). Empty list means
    no multimodal artifacts for this identity (not an error).
    """
    details = (store or get_default_store()).list_details(
        run_id=run_id, question_id=question_id, version_id=version_id
    )
    return [d.artifact for d in details]


def list_multimodal_details(
    *,
    run_id: str,
    question_id: str,
    version_id: str,
    store: MultimodalArtifactStore | None = None,
) -> list[MultimodalDetailView]:
    """Detail projection including public_source and needs_human_review."""
    return (store or get_default_store()).list_details(
        run_id=run_id, question_id=question_id, version_id=version_id
    )


__all__ = [
    "T06_LOW_CONFIDENCE_THRESHOLD",
    "MultimodalPortError",
    "PublicSourceRef",
    "MultimodalDetailView",
    "MultimodalArtifactStore",
    "get_default_store",
    "put_multimodal_artifact",
    "list_multimodal_artifacts",
    "list_multimodal_details",
    "build_public_source",
]
