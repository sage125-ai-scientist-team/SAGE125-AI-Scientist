"""Open-access fulltext fetch with fail-closed validation. No paywall bypass."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.evidence.eligibility import SourceEligibility

_ARXIV_ABS = re.compile(
    r"(?:arxiv\.org/(?:abs|pdf)/|arxiv:)"
    r"(?P<id>(?:[a-z-]+(?:\.[A-Z]{2})?/\d{7}|\d{4}\.\d{4,5}))(?:v\d+)?",
    re.IGNORECASE,
)
_CAPTCHA_MARKERS = ("captcha", "cf-challenge", "just a moment", "access denied")
_LOGIN_MARKERS = ("sign in", "log in", "subscribe to continue", "purchase this")
MIN_PDF_BYTES = 2048
MIN_TEXT_CHARS = 400
USER_AGENT = "SAGE125-evidence-remediation/1.0"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def arxiv_id_from_url(url: str | None) -> str | None:
    if not url:
        return None
    match = _ARXIV_ABS.search(url)
    return match.group("id") if match else None


def arxiv_pdf_url(arxiv_id: str) -> str:
    return f"https://arxiv.org/pdf/{arxiv_id}.pdf"


def is_login_or_captcha_html(text: str) -> bool:
    lowered = text[:4000].casefold()
    return any(marker in lowered for marker in (*_CAPTCHA_MARKERS, *_LOGIN_MARKERS))


def validate_pdf_bytes(payload: bytes) -> str | None:
    if not payload.startswith(b"%PDF"):
        return "not_pdf_magic"
    if len(payload) < MIN_PDF_BYTES:
        return "pdf_too_small"
    return None


def extract_pdf_pages(payload: bytes) -> list[dict[str, Any]]:
    from pypdf import PdfReader
    from io import BytesIO

    reader = PdfReader(BytesIO(payload))
    pages: list[dict[str, Any]] = []
    for index, page in enumerate(reader.pages, start=1):
        text = " ".join((page.extract_text() or "").split())
        if text:
            pages.append({"page": index, "text": text})
    return pages


def select_quote(pages: list[dict[str, Any]], keywords: list[str]) -> dict[str, Any] | None:
    lowered_keys = [item.casefold() for item in keywords if len(item) >= 4]
    candidates: list[dict[str, Any]] = []
    for page in pages[:8]:
        text = page["text"]
        sentences = re.split(r"(?<=[.!?])\s+", text)
        buffer = ""
        for sentence in sentences:
            buffer = (buffer + " " + sentence).strip()
            if 180 <= len(buffer) <= 700:
                score = sum(1 for key in lowered_keys if key in buffer.casefold())
                candidates.append(
                    {
                        "quote": buffer,
                        "page": page["page"],
                        "section": f"page-{page['page']}",
                        "paragraph": 1,
                        "keyword_hits": score,
                    }
                )
                buffer = ""
        if 180 <= len(text[:500]) <= 1200 and not candidates:
            candidates.append(
                {
                    "quote": text[:500],
                    "page": page["page"],
                    "section": f"page-{page['page']}",
                    "paragraph": 1,
                    "keyword_hits": sum(1 for key in lowered_keys if key in text[:500].casefold()),
                }
            )
    if not candidates:
        return None
    candidates.sort(key=lambda item: (-item["keyword_hits"], item["page"]))
    return candidates[0]


class FulltextFetchAudit:
    def __init__(self) -> None:
        self.discovery_requests = 0
        self.fetch_requests = 0
        self.fetch_succeeded = 0
        self.fetch_failed = 0
        self.events: list[dict[str, Any]] = []

    def record(self, event: dict[str, Any]) -> None:
        self.events.append({"at": utc_now(), **event})

    def snapshot(self) -> dict[str, Any]:
        return {
            "literature_discovery_requests": self.discovery_requests,
            "fulltext_fetch_requests": self.fetch_requests,
            "fulltext_fetch_succeeded": self.fetch_succeeded,
            "fulltext_fetch_failed": self.fetch_failed,
            "events": self.events[-200:],
        }


def _http_get(url: str, timeout: int = 45) -> tuple[int, str, bytes, list[str]]:
    import requests

    response = requests.get(
        url,
        timeout=timeout,
        headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
        allow_redirects=True,
    )
    chain = [str(item.url) for item in response.history] + [str(response.url)]
    return response.status_code, str(response.headers.get("Content-Type") or ""), response.content, chain


def fetch_arxiv_pdf(
    *,
    arxiv_id: str,
    cache_root: Path,
    audit: FulltextFetchAudit,
) -> dict[str, Any]:
    url = arxiv_pdf_url(arxiv_id)
    audit.fetch_requests += 1
    try:
        status, content_type, payload, chain = _http_get(url)
    except Exception as exc:
        audit.fetch_failed += 1
        audit.record({"kind": "arxiv_pdf", "id": arxiv_id, "status": "FETCH_FAILED", "error": type(exc).__name__})
        return {"eligibility": SourceEligibility.FETCH_FAILED.value, "arxiv_id": arxiv_id, "url": url}
    pdf_error = validate_pdf_bytes(payload)
    if status != 200 or pdf_error:
        audit.fetch_failed += 1
        audit.record({"kind": "arxiv_pdf", "id": arxiv_id, "status": "FETCH_FAILED", "http": status, "error": pdf_error})
        return {
            "eligibility": SourceEligibility.FETCH_FAILED.value,
            "arxiv_id": arxiv_id,
            "url": url,
            "http_status": status,
        }
    digest = sha256_bytes(payload)
    item_dir = cache_root / digest[:2] / digest
    item_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = item_dir / "original.pdf"
    if not pdf_path.exists():
        pdf_path.write_bytes(payload)
    try:
        pages = extract_pdf_pages(payload)
    except Exception as exc:
        audit.fetch_failed += 1
        audit.record({"kind": "arxiv_pdf", "id": arxiv_id, "status": "FETCH_FAILED", "error": type(exc).__name__})
        return {"eligibility": SourceEligibility.FETCH_FAILED.value, "arxiv_id": arxiv_id, "url": url}
    full_text = "\n\n".join(page["text"] for page in pages)
    if len(full_text) < MIN_TEXT_CHARS:
        audit.fetch_failed += 1
        return {"eligibility": SourceEligibility.FETCH_FAILED.value, "arxiv_id": arxiv_id, "reason": "too_little_text"}
    parsed = {"page_count": len(pages), "char_count": len(full_text), "pages": pages}
    (item_dir / "parsed_text.json").write_text(json.dumps(parsed, ensure_ascii=False), encoding="utf-8")
    locator_map = [{"page": page["page"], "section": f"page-{page['page']}"} for page in pages]
    (item_dir / "locator_map.json").write_text(json.dumps(locator_map, ensure_ascii=False), encoding="utf-8")
    source_manifest = {
        "source_id": f"arxiv:{arxiv_id}",
        "source_url": url,
        "landing_url": f"https://arxiv.org/abs/{arxiv_id}",
        "content_type": content_type,
        "content_sha256": digest,
        "version": "submittedVersion",
        "license_or_access": "arxiv_open_access",
        "redirect_chain": chain,
        "fetched_at": utc_now(),
        "domain": urlparse(chain[-1]).netloc if chain else "arxiv.org",
    }
    (item_dir / "source_manifest.json").write_text(json.dumps(source_manifest, indent=2), encoding="utf-8")
    fetch_audit = {"http_status": status, "content_type": content_type, "bytes": len(payload), "chain": chain}
    (item_dir / "fetch_audit.json").write_text(json.dumps(fetch_audit, indent=2), encoding="utf-8")
    (item_dir / "checksums.sha256").write_text(f"{digest}  original.pdf\n", encoding="utf-8")
    audit.fetch_succeeded += 1
    audit.record({"kind": "arxiv_pdf", "id": arxiv_id, "status": "FULLTEXT_VERIFIED", "sha256": digest})
    return {
        "eligibility": SourceEligibility.FULLTEXT_VERIFIED.value,
        "arxiv_id": arxiv_id,
        "url": url,
        "content_sha256": digest,
        "cache_dir": str(item_dir),
        "pages": pages,
        "source_manifest": source_manifest,
        "title": "",
    }
