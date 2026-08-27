"""Single official 125-question catalog used by API, UI, and indexes.

The packaged mapping is derived from the booklet extract
``data/processed/questions_125.json`` (SHA pinned by T07/T09) but omits
``booklet_excerpt`` so it can ship in the deploy package. Formal mode must
never fall back to Preview Seed.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CATALOG_PATH = PROJECT_ROOT / "data" / "catalog" / "official_questions_125.json"
QID_RE = re.compile(r"^Q(\d{3})$")
EXPECTED_IDS = [f"Q{i:03d}" for i in range(1, 126)]
Q028_OFFICIAL_TITLE = "Will it be possible to cure all cancers?"
PREVIEW_MARKERS = ("[PREVIEW-SEED]", "placeholder question", "preview_seed")


@dataclass(frozen=True)
class OfficialQuestion:
    question_id: str
    title_en: str
    title_zh: str
    domain: str
    source_page: int | None
    source_type: str
    catalog_version: str

    def display_title(self) -> str:
        zh = (self.title_zh or "").strip()
        return zh or self.title_en

    def selector_label(self) -> str:
        return f"{self.question_id} · {self.display_title()}"

    def as_api_item(self, digest: str) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "id": self.question_id,
            "title_en": self.title_en,
            "title_zh": self.title_zh,
            "question": self.title_en,
            "domain": self.domain,
            "source_page": self.source_page,
            "source_type": self.source_type,
            "catalog_source": "official",
            "catalog_digest": digest,
            "catalog_version": self.catalog_version,
        }


class OfficialQuestionCatalog:
    """Validated in-memory official catalog."""

    def __init__(self, questions: list[OfficialQuestion], *, digest: str, path: Path, version: str):
        self.questions = questions
        self.digest = digest
        self.path = path
        self.version = version
        self._by_id = {item.question_id: item for item in questions}

    def get_question(self, question_id: str | None) -> OfficialQuestion | None:
        if not question_id:
            return None
        return self._by_id.get(str(question_id).strip().upper())

    def list_questions(self) -> list[OfficialQuestion]:
        return list(self.questions)

    def get_catalog_digest(self) -> str:
        return self.digest

    def question_ids(self) -> list[str]:
        return [item.question_id for item in self.questions]


def official_catalog_path() -> Path:
    override = os.getenv("SAGE125_CATALOG_PATH", "").strip()
    if override:
        return Path(override)
    return DEFAULT_CATALOG_PATH


def allow_preview_seed() -> bool:
    """Preview Seed is opt-in for local development only."""
    app_env = os.getenv("APP_ENV", "").strip().lower()
    flag = os.getenv("SAGE125_ALLOW_PREVIEW_SEED", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    return app_env == "development" and flag


def _contains_preview_marker(blob: str) -> bool:
    lowered = blob.lower()
    return any(marker.lower() in lowered for marker in PREVIEW_MARKERS)


def _canonical_digest(rows: list[dict[str, Any]]) -> str:
    canonical = [
        {
            "question_id": row["question_id"],
            "title_en": row["title_en"],
            "domain": row["domain"],
        }
        for row in rows
    ]
    payload = json.dumps(canonical, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_catalog(payload: dict[str, Any] | list[Any]) -> list[OfficialQuestion]:
    if isinstance(payload, list):
        raw_items = payload
        version = "unknown"
    elif isinstance(payload, dict):
        raw_items = payload.get("questions") or []
        version = str(payload.get("catalog_version") or "sjtu-booklet-125-v1")
        if str(payload.get("catalog_source") or "official") != "official":
            raise ValueError("catalog_source must be official")
    else:
        raise ValueError("catalog payload must be an object or list")
    if not isinstance(raw_items, list) or len(raw_items) != 125:
        raise ValueError("official catalog must contain exactly 125 questions")

    questions: list[OfficialQuestion] = []
    seen: set[str] = set()
    for raw in raw_items:
        if not isinstance(raw, dict):
            raise ValueError("catalog item must be an object")
        qid = str(raw.get("question_id") or raw.get("id") or "").strip().upper()
        title = str(raw.get("title_en") or raw.get("question") or "").strip()
        domain = str(raw.get("domain") or "").strip()
        if QID_RE.fullmatch(qid) is None:
            raise ValueError(f"invalid question_id: {qid}")
        if qid in seen:
            raise ValueError(f"duplicate question_id: {qid}")
        if not title or _contains_preview_marker(title):
            raise ValueError(f"invalid official title for {qid}")
        if not domain or _contains_preview_marker(domain):
            raise ValueError(f"invalid official domain for {qid}")
        if _contains_preview_marker(json.dumps(raw, ensure_ascii=False)):
            raise ValueError(f"preview marker in official catalog item {qid}")
        seen.add(qid)
        page = raw.get("source_page")
        questions.append(
            OfficialQuestion(
                question_id=qid,
                title_en=title,
                title_zh=str(raw.get("title_zh") or "").strip(),
                domain=domain,
                source_page=int(page) if str(page or "").isdigit() else None,
                source_type=str(raw.get("source_type") or "official_booklet"),
                catalog_version=version,
            )
        )
    ids = [item.question_id for item in questions]
    if ids != EXPECTED_IDS:
        missing = [qid for qid in EXPECTED_IDS if qid not in seen]
        extra = [qid for qid in ids if qid not in EXPECTED_IDS]
        raise ValueError(f"catalog ids incomplete missing={missing} extra={extra}")
    q028 = next(item for item in questions if item.question_id == "Q028")
    if q028.title_en != Q028_OFFICIAL_TITLE:
        raise ValueError("Q028 official title mismatch")
    return questions


@lru_cache(maxsize=8)
def _load_cached(path_key: str, mtime: float) -> OfficialQuestionCatalog:
    path = Path(path_key)
    payload = json.loads(path.read_text(encoding="utf-8"))
    questions = validate_catalog(payload)
    rows = [
        {"question_id": item.question_id, "title_en": item.title_en, "domain": item.domain}
        for item in questions
    ]
    digest = (
        str(payload.get("catalog_digest"))
        if isinstance(payload, dict) and payload.get("catalog_digest")
        else _canonical_digest(rows)
    )
    version = questions[0].catalog_version if questions else "unknown"
    return OfficialQuestionCatalog(questions, digest=digest, path=path, version=version)


def load_official_catalog(path: Path | None = None) -> OfficialQuestionCatalog:
    catalog_path = path or official_catalog_path()
    if not catalog_path.exists():
        raise FileNotFoundError(f"official catalog missing: {catalog_path}")
    return _load_cached(str(catalog_path.resolve()), catalog_path.stat().st_mtime)


def get_question(question_id: str | None) -> OfficialQuestion | None:
    return load_official_catalog().get_question(question_id)


def list_questions() -> list[OfficialQuestion]:
    return load_official_catalog().list_questions()


def get_catalog_digest() -> str:
    return load_official_catalog().get_catalog_digest()


def clear_catalog_cache() -> None:
    _load_cached.cache_clear()
