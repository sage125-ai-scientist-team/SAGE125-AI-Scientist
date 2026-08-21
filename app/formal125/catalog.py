"""Source-controlled Q001-Q125 catalog, booklet domains, and frozen selections."""

from __future__ import annotations

import hashlib
import json
import random
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from app.batch.five_run_preflight import FROZEN_QUESTION_IDS
from app.formal125 import EXPECTED_QUESTION_COUNT
from app.formal125.hashes import sha256_bytes, sha256_canonical_json, sha256_file, write_json


AUTHORITATIVE_SOURCE_SHA256 = (
    "b6712a3b53f9776d7f695ea67f810c30b7d97ee59c183009432870d3224cdebb"
)
AUTHORITATIVE_PDF_SHA256 = (
    "4bda50e8e3c90f8968f1bfd72ded4d9587ae80cd40ba66656a12c93abcf8e576"
)
CATALOG_SCHEMA_VERSION = "formal125.catalog.v1"
DOMAIN_SCHEMA_VERSION = "formal125.domain-map.v1"
SELECTION_SEED = 20260821

BOOKLET_DOMAINS: tuple[str, ...] = (
    "Mathematical Sciences",
    "Chemistry",
    "Medicine & Health",
    "Biology",
    "Astronomy",
    "Physics",
    "Engineering & Materials Science",
    "Information Science",
    "Neuroscience",
    "Ecology",
    "Energy Science",
    "Artificial Intelligence",
)
BOOKLET_DOMAIN_COUNT = len(BOOKLET_DOMAINS)

T09_DOMAIN_REPRESENTATIVES: tuple[tuple[str, str, str], ...] = (
    ("Q001", "mathematics", "Mathematical Sciences"),
    ("Q069", "physics", "Physics"),
    ("Q003", "chemistry", "Chemistry"),
    ("Q026", "biology", "Biology"),
    ("Q013", "medicine", "Medicine & Health"),
    ("Q109", "earth_science", "Ecology"),
    ("Q091", "computer_science", "Information Science"),
    ("Q089", "materials", "Engineering & Materials Science"),
    ("Q046", "astronomy", "Astronomy"),
    ("Q095", "neuroscience", "Neuroscience"),
    ("Q107", "climate", "Ecology"),
    ("Q088", "engineering", "Engineering & Materials Science"),
)

QUESTION_ID_RE = re.compile(r"^Q\d{3}$")


class CatalogError(ValueError):
    """Raised when the official 125 catalog cannot be frozen."""


def domain_id_from_booklet(name: str) -> str:
    slug = name.strip().lower().replace("&", "and")
    slug = re.sub(r"[^a-z0-9]+", "_", slug).strip("_")
    return slug


def _ordinal(question_id: str) -> int:
    return int(question_id[1:])


def load_source_records(source_path: Path) -> list[dict[str, Any]]:
    raw = source_path.read_bytes()
    digest = sha256_bytes(raw)
    if digest != AUTHORITATIVE_SOURCE_SHA256:
        raise CatalogError(
            f"questions source SHA-256 {digest} != {AUTHORITATIVE_SOURCE_SHA256}"
        )
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, list):
        raise CatalogError("questions source must be a JSON list")
    return payload


def normalize_question(record: Mapping[str, Any], index: int) -> dict[str, Any]:
    question_id = str(record.get("id") or "").strip()
    title = str(record.get("question") or "").strip()
    excerpt = str(record.get("booklet_excerpt") or "").strip()
    domain = str(record.get("domain") or "").strip()
    page = record.get("source_page")
    if not QUESTION_ID_RE.fullmatch(question_id):
        raise CatalogError(f"invalid question id at index {index}: {question_id!r}")
    if _ordinal(question_id) != index + 1:
        raise CatalogError(
            f"question id {question_id} is not contiguous at ordinal {index + 1}"
        )
    if not title:
        raise CatalogError(f"{question_id} is missing the official English title")
    original_text = excerpt or title
    if domain not in BOOKLET_DOMAINS:
        raise CatalogError(f"{question_id} has unknown booklet domain {domain!r}")
    question_hash = sha256_canonical_json(
        {
            "question_id": question_id,
            "original_title": title,
            "original_question_text": original_text,
            "booklet_excerpt": excerpt,
            "domain": domain,
        }
    )
    return {
        "question_id": question_id,
        "ordinal": index + 1,
        "original_title": title,
        "original_question_text": original_text,
        "booklet_excerpt": excerpt,
        "booklet_excerpt_present": bool(excerpt),
        "normalized_title": title,
        "domain_id": domain_id_from_booklet(domain),
        "booklet_domain": domain,
        "source_locator": {
            "source_name": "125 Questions: Exploration and Discovery",
            "source_file": "data/raw/sjtu-booklet.pdf",
            "source_page": page,
            "source_pdf_sha256": AUTHORITATIVE_PDF_SHA256,
        },
        "question_hash": question_hash,
        "evidence_eligible": False,
    }


def build_catalog_lock(source_path: Path, *, generated_at: str | None = None) -> dict[str, Any]:
    records = load_source_records(source_path)
    if len(records) != EXPECTED_QUESTION_COUNT:
        raise CatalogError(f"expected 125 questions, found {len(records)}")
    questions = [normalize_question(record, index) for index, record in enumerate(records)]
    ids = [item["question_id"] for item in questions]
    titles = [item["original_title"] for item in questions]
    duplicate_ids = sorted({qid for qid in ids if ids.count(qid) > 1})
    duplicate_titles = sorted({title for title in titles if titles.count(title) > 1})
    if duplicate_ids:
        raise CatalogError(f"duplicate question ids: {duplicate_ids}")
    expected_ids = [f"Q{index:03d}" for index in range(1, EXPECTED_QUESTION_COUNT + 1)]
    missing = [qid for qid in expected_ids if qid not in ids]
    if missing:
        raise CatalogError(f"missing question ids: {missing}")
    payload = {
        "catalog_schema_version": CATALOG_SCHEMA_VERSION,
        "source_name": "data/processed/questions_125.json",
        "source_sha256": AUTHORITATIVE_SOURCE_SHA256,
        "source_pdf_sha256": AUTHORITATIVE_PDF_SHA256,
        "question_count": len(questions),
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "title_uniqueness_note": (
            "Official English titles are preserved verbatim. Duplicate titles "
            "are reported rather than rewritten."
            if duplicate_titles
            else "All official English titles are unique."
        ),
        "duplicate_titles": duplicate_titles,
        "questions": questions,
        "booklet_is_question_source_only": True,
        "evidence_eligible_default": False,
    }
    payload["catalog_sha256"] = sha256_canonical_json(
        {key: value for key, value in payload.items() if key != "catalog_sha256"}
    )
    return payload


def build_domain_map(catalog: Mapping[str, Any]) -> dict[str, Any]:
    questions = list(catalog["questions"])
    grouped: dict[str, list[str]] = {domain_id_from_booklet(name): [] for name in BOOKLET_DOMAINS}
    seen: set[str] = set()
    q028_domain = None
    for item in questions:
        domain_id = item["domain_id"]
        qid = item["question_id"]
        if qid in seen:
            raise CatalogError(f"question assigned twice: {qid}")
        seen.add(qid)
        grouped[domain_id].append(qid)
        if qid == "Q028":
            q028_domain = domain_id
    covered = sum(len(values) for values in grouped.values())
    if covered != EXPECTED_QUESTION_COUNT:
        raise CatalogError("domain map does not cover 125 questions")
    empty = [domain_id for domain_id, values in grouped.items() if not values]
    if empty:
        raise CatalogError(f"empty booklet domains: {empty}")
    if q028_domain is None:
        raise CatalogError("Q028 is missing from the domain map")
    payload = {
        "domain_schema_version": DOMAIN_SCHEMA_VERSION,
        "mapping_source": (
            "Official booklet domain headings preserved in the SHA-256-pinned "
            "questions_125.json extraction. No model reclassification."
        ),
        "domain_count": BOOKLET_DOMAIN_COUNT,
        "domains": [
            {
                "domain_id": domain_id_from_booklet(name),
                "domain_name": name,
                "question_ids": grouped[domain_id_from_booklet(name)],
            }
            for name in BOOKLET_DOMAINS
        ],
        "q028_domain_id": q028_domain,
        "q028_domain_name": "Biology",
        "t09_evaluation_taxonomy_note": (
            "T09 uses a different 12-domain evaluation taxonomy that currently "
            "has captain-approved representatives for 12 questions only. That "
            "taxonomy is recorded in formal_12_domain_selection_manifest.json "
            "and is not silently merged into this complete 125 mapping."
        ),
        "t09_representative_only": [
            {
                "question_id": qid,
                "t09_domain_id": t09_domain,
                "booklet_domain": booklet,
            }
            for qid, t09_domain, booklet in T09_DOMAIN_REPRESENTATIVES
        ],
    }
    payload["domain_map_sha256"] = sha256_canonical_json(
        {key: value for key, value in payload.items() if key != "domain_map_sha256"}
    )
    return payload


def build_formal_5_manifest(catalog: Mapping[str, Any]) -> dict[str, Any]:
    by_id = {item["question_id"]: item for item in catalog["questions"]}
    selected = []
    domains: list[str] = []
    for qid in FROZEN_QUESTION_IDS:
        item = by_id[qid]
        selected.append(
            {
                "question_id": qid,
                "domain_id": item["domain_id"],
                "booklet_domain": item["booklet_domain"],
                "original_title": item["original_title"],
                "question_hash": item["question_hash"],
            }
        )
        domains.append(item["domain_id"])
    if "Q028" not in FROZEN_QUESTION_IDS:
        raise CatalogError("formal 5 must include Q028")
    if len(set(domains)) < 4:
        raise CatalogError("formal 5 must span multiple booklet domains")
    biomedical = {"biology", "medicine_and_health"}
    if set(domains).issubset(biomedical):
        raise CatalogError("formal 5 cannot be all biomedical")
    payload = {
        "selection_id": "formal-5-t07-wb5-reuse",
        "policy": "Reuse captain-frozen T07-WB5-20260807-v2 IDs; do not reselect by model quality.",
        "seed": None,
        "source_freeze": "T07-WB5-20260807-v2",
        "question_ids": list(FROZEN_QUESTION_IDS),
        "questions": selected,
        "includes_q028": True,
        "biomedical_only": False,
    }
    payload["selection_sha256"] = sha256_canonical_json(
        {key: value for key, value in payload.items() if key != "selection_sha256"}
    )
    return payload


def build_formal_12_manifest(catalog: Mapping[str, Any]) -> dict[str, Any]:
    by_id = {item["question_id"]: item for item in catalog["questions"]}
    selected = []
    t09_domains: list[str] = []
    for qid, t09_domain, booklet in T09_DOMAIN_REPRESENTATIVES:
        item = by_id[qid]
        selected.append(
            {
                "question_id": qid,
                "t09_domain_id": t09_domain,
                "booklet_domain": item["booklet_domain"],
                "original_title": item["original_title"],
                "question_hash": item["question_hash"],
                "source": "docs/reproducibility/T09_12_DOMAIN_ACTUAL_INPUT_MANIFEST.json",
            }
        )
        t09_domains.append(t09_domain)
    if len(set(t09_domains)) != 12:
        raise CatalogError("T09 representative selection does not cover 12 evaluation domains")
    payload = {
        "selection_id": "formal-12-t09-reuse",
        "policy": "Reuse captain-approved T09 12-domain representatives; no model reselection.",
        "question_ids": [row[0] for row in T09_DOMAIN_REPRESENTATIVES],
        "questions": selected,
    }
    payload["selection_sha256"] = sha256_canonical_json(
        {key: value for key, value in payload.items() if key != "selection_sha256"}
    )
    return payload


def build_manual_review_24_manifest(catalog: Mapping[str, Any]) -> dict[str, Any]:
    by_domain: dict[str, list[str]] = defaultdict(list)
    for item in catalog["questions"]:
        by_domain[item["domain_id"]].append(item["question_id"])
    required = set(FROZEN_QUESTION_IDS)
    required.update(qid for qid, _, _ in T09_DOMAIN_REPRESENTATIVES)
    required.add("Q028")
    selected: list[str] = []
    proof: list[dict[str, Any]] = []
    for qid in sorted(required, key=_ordinal):
        selected.append(qid)
        proof.append({"question_id": qid, "reason": "frozen_required_set"})
    id_to_domain = {
        item["question_id"]: item["domain_id"] for item in catalog["questions"]
    }
    covered = {id_to_domain[qid] for qid in selected}
    remaining_by_domain = {
        domain_id: [qid for qid in qids if qid not in selected]
        for domain_id, qids in by_domain.items()
    }
    domain_cycle = [domain_id_from_booklet(name) for name in BOOKLET_DOMAINS]
    for domain_id in domain_cycle:
        if domain_id in covered:
            continue
        pool = remaining_by_domain[domain_id]
        if not pool:
            raise CatalogError(f"no remaining question for domain {domain_id}")
        choice = pool[0]
        selected.append(choice)
        remaining_by_domain[domain_id] = pool[1:]
        covered.add(domain_id)
        proof.append(
            {
                "question_id": choice,
                "reason": "domain_coverage",
                "domain_id": domain_id,
            }
        )
    rng = random.Random(SELECTION_SEED)
    while len(selected) < 24:
        progressed = False
        for domain_id in domain_cycle:
            pool = [qid for qid in remaining_by_domain[domain_id] if qid not in selected]
            if not pool:
                continue
            choice = pool[rng.randrange(len(pool))]
            selected.append(choice)
            remaining_by_domain[domain_id] = [qid for qid in pool if qid != choice]
            proof.append(
                {
                    "question_id": choice,
                    "reason": "stratified_no_replacement",
                    "domain_id": domain_id,
                    "seed": SELECTION_SEED,
                }
            )
            progressed = True
            if len(selected) >= 24:
                break
        if not progressed:
            raise CatalogError("unable to complete 24-question stratified sample")
    selected = sorted(set(selected), key=_ordinal)
    if len(selected) < 24:
        raise CatalogError("manual review list is shorter than 24")
    if "Q028" not in selected:
        raise CatalogError("manual review list must include Q028")
    covered_domains = {
        item["domain_id"]
        for item in catalog["questions"]
        if item["question_id"] in selected
    }
    if len(covered_domains) != BOOKLET_DOMAIN_COUNT:
        raise CatalogError("manual review list does not cover 12 booklet domains")
    payload = {
        "selection_id": "manual-review-24-stratified",
        "policy": "Union of frozen 5 + T09 12, plus stratified no-replacement fill with seed 20260821.",
        "seed": SELECTION_SEED,
        "replacement": False,
        "question_ids": selected,
        "count": len(selected),
        "includes_q028": True,
        "selection_proof": proof,
    }
    payload["selection_sha256"] = sha256_canonical_json(
        {key: value for key, value in payload.items() if key != "selection_sha256"}
    )
    return payload


def production_source_records(catalog: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Adapter for T07 BatchRunner which requires question_id rather than id."""

    return [
        {
            "question_id": item["question_id"],
            "domain": item["booklet_domain"],
            "question": item["original_title"],
            "booklet_excerpt": item.get("booklet_excerpt") or item["original_question_text"],
            "question_hash": item["question_hash"],
            "evidence_eligible": False,
        }
        for item in catalog["questions"]
    ]


def write_production_source(catalog: Mapping[str, Any], path: Path) -> Path:
    write_json(path, production_source_records(catalog))
    return path
