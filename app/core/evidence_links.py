"""Build safe, canonical links for externally verifiable evidence.

Raw URLs from model output or imported artifacts are never placed directly in
HTML.  A link is exposed only when its source and identifier can be rebuilt
into a known HTTPS destination (DOI, arXiv, or OpenAlex).
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping
from urllib.parse import quote, urlparse


_DOI_RE = re.compile(r"^10\.\d{4,9}/[-._;()/:A-Z0-9+]+$", re.IGNORECASE)
_ARXIV_ID_RE = re.compile(
    r"^(?:\d{4}\.\d{4,5}|[a-z][a-z.-]+/\d{7})(?:v\d+)?$",
    re.IGNORECASE,
)
_OPENALEX_ID_RE = re.compile(r"^W\d+$", re.IGNORECASE)
_DOI_SOURCES = frozenset({"arxiv", "openalex", "crossref"})


@dataclass(frozen=True)
class CanonicalEvidenceLink:
    """A trusted outbound evidence link reconstructed from a stable ID."""

    url: str
    display: str
    label: str
    kind: str


def _as_mapping(card: Any) -> Mapping[str, Any]:
    if isinstance(card, Mapping):
        return card
    dump = getattr(card, "model_dump", None)
    return dump() if callable(dump) else {}


def normalize_doi(value: Any) -> str | None:
    """Return a safe DOI identifier, rejecting whitespace and HTML/URL syntax."""

    text = str(value or "").strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if text.lower().startswith(prefix):
            text = text[len(prefix):].strip()
            break
    if not _DOI_RE.fullmatch(text):
        return None
    return text


def _arxiv_id(card: Mapping[str, Any]) -> str | None:
    for value in (card.get("url"), card.get("id")):
        text = str(value or "").strip()
        if _ARXIV_ID_RE.fullmatch(text):
            return text
        parsed = urlparse(text)
        if parsed.scheme not in {"http", "https"} or (parsed.hostname or "").lower() not in {
            "arxiv.org",
            "www.arxiv.org",
            "export.arxiv.org",
        }:
            continue
        match = re.fullmatch(
            r"/(?:abs|pdf)/((?:[a-z-]+(?:\.[A-Za-z]{2})?/\d{7}|\d{4}\.\d{4,5})(?:v\d+)?)(?:\.pdf)?",
            parsed.path,
            flags=re.IGNORECASE,
        )
        if match and _ARXIV_ID_RE.fullmatch(match.group(1)):
            return match.group(1)
    return None


def _openalex_id(card: Mapping[str, Any]) -> str | None:
    for value in (card.get("id"), card.get("url")):
        text = str(value or "").strip()
        if _OPENALEX_ID_RE.fullmatch(text):
            return text.upper()
        parsed = urlparse(text)
        if parsed.scheme not in {"http", "https"} or (parsed.hostname or "").lower() not in {
            "openalex.org",
            "www.openalex.org",
        }:
            continue
        candidate = parsed.path.strip("/")
        if _OPENALEX_ID_RE.fullmatch(candidate):
            return candidate.upper()
    return None


def canonical_evidence_link(card: Any) -> CanonicalEvidenceLink | None:
    """Return a canonical HTTPS link only for trusted literature identifiers.

    DOI takes precedence because it resolves to the publisher record.  arXiv
    and OpenAlex URLs are rebuilt from validated IDs.  DeepResearch, RAG,
    uploaded files and mock evidence never receive an outbound link here.
    """

    data = _as_mapping(card)
    source = str(data.get("source_type") or "").strip().lower()
    note = str(data.get("reliability_note") or "").lower()
    if "mock_for_testing" in note:
        return None

    if source in _DOI_SOURCES:
        doi = normalize_doi(data.get("doi"))
        if doi:
            encoded = quote(doi, safe="/._;():+-")
            return CanonicalEvidenceLink(
                url=f"https://doi.org/{encoded}",
                display=doi,
                label="打开 DOI",
                kind="doi",
            )

    if source == "arxiv":
        identifier = _arxiv_id(data)
        if identifier:
            return CanonicalEvidenceLink(
                url=f"https://arxiv.org/abs/{identifier}",
                display=f"arXiv:{identifier}",
                label="查看 arXiv",
                kind="arxiv",
            )

    if source == "openalex":
        identifier = _openalex_id(data)
        if identifier:
            return CanonicalEvidenceLink(
                url=f"https://openalex.org/{identifier}",
                display=f"OpenAlex {identifier}",
                label="查看 OpenAlex",
                kind="openalex",
            )
    return None


def evidence_verification_note(card: Any) -> str:
    """Return a concise user-facing provenance/verification caveat."""

    data = _as_mapping(card)
    source = str(data.get("source_type") or "").strip().lower()
    note = str(data.get("reliability_note") or "").lower()
    if "mock_for_testing" in note:
        return "模拟证据：不存在外部原文链接"
    if source == "arxiv":
        return "arXiv 摘要可核验；预印本不一定经过同行评审"
    if source == "openalex":
        return "OpenAlex 元数据候选；请打开 DOI/原文核验内容"
    if source == "crossref":
        return "Crossref 元数据候选；请打开 DOI/原文核验内容"
    if source == "deep_research":
        return "DeepResearch 候选；尚未经过独立文献核验"
    if source in {"rag", "booklet", "user_upload"}:
        return "本地资料片段；无外部文献链接"
    return "来源状态未知；请人工核验"


__all__ = [
    "CanonicalEvidenceLink",
    "canonical_evidence_link",
    "evidence_verification_note",
    "normalize_doi",
]
