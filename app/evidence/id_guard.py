"""Unknown Evidence ID guard: parse-time fail-closed, no fuzzy repair."""

from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable, Mapping

from app.evidence.eligibility import FORBIDDEN_EVIDENCE_ID_PATTERNS

_EVIDENCE_ID_KEYS = (
    "evidence_ids",
    "reference_ids",
    "supporting_evidence_ids",
    "contradicted_by_evidence_ids",
)
_FORBIDDEN_RE = tuple(re.compile(pattern) for pattern in FORBIDDEN_EVIDENCE_ID_PATTERNS)


class UnknownEvidenceIDError(ValueError):
    """Raised when a model output cites an ID outside the allowed bundle."""


def deterministic_evidence_id(
    *,
    question_id: str,
    content_sha256: str,
    locator: str,
    quote: str,
) -> str:
    payload = "|".join(
        [
            question_id.strip(),
            content_sha256.strip().lower(),
            " ".join(locator.split()),
            hashlib.sha256(" ".join(quote.split()).encode("utf-8")).hexdigest(),
        ]
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"EV-{question_id}-{digest}"


def is_forbidden_evidence_id(evidence_id: str) -> bool:
    value = str(evidence_id or "").strip()
    return any(pattern.fullmatch(value) for pattern in _FORBIDDEN_RE)


def collect_cited_evidence_ids(obj: Any) -> list[str]:
    found: list[str] = []

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in _EVIDENCE_ID_KEYS and isinstance(value, list):
                    found.extend(str(item) for item in value if str(item).strip())
                else:
                    _walk(value)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(obj)
    return list(dict.fromkeys(found))


def assert_known_evidence_ids(
    payload: Mapping[str, Any] | list[Any],
    allowed_ids: Iterable[str],
    *,
    raw_output: Any | None = None,
) -> list[str]:
    allowed = {str(item).strip() for item in allowed_ids if str(item).strip()}
    cited = collect_cited_evidence_ids(payload)
    unknown = [item for item in cited if item not in allowed]
    forbidden = [item for item in cited if is_forbidden_evidence_id(item)]
    if unknown or forbidden:
        raise UnknownEvidenceIDError(
            "UNKNOWN_EVIDENCE_ID:"
            + ",".join(dict.fromkeys([*unknown, *forbidden]))
        )
    del raw_output
    return cited
