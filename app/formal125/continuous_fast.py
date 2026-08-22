"""Thin Formal 125 continuous-fast orchestration. Does not change scientific gates."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from app.evidence.relevance import GENERIC_BANNED, SPEC_TEMPLATES
from app.exporters.pdf_exporter import export_markdown_to_pdf
from app.formal125 import REQUIRED_RESULT_FILES
from app.formal125.authorization import compute_authorization_hash
from app.formal125.hashes import sha256_canonical_json, sha256_file
from app.formal125.actual_run import atomic_write_json, atomic_write_text


STAMP = "20260822-155218"
SCIENTIFIC_PRODUCER_SHA = "c465f718607536b87f55f37b691cd5dedb401825"
METADATA_COMMIT_SHA = "3aa83d163ea39eed82aa1432cba17bdd387496c1"
PROJECT_PROVIDER_CALLS_BEFORE = 239

REUSED_CASE_IDS: tuple[str, ...] = (
    "Q001",
    "Q003",
    "Q013",
    "Q026",
    "Q028",
    "Q046",
    "Q050",
    "Q069",
    "Q075",
    "Q088",
    "Q089",
    "Q091",
    "Q095",
    "Q107",
    "Q109",
)
PARTIAL_REUSED_IDS = frozenset({"Q095"})
MANUAL_REVIEW_24: tuple[str, ...] = (
    "Q001",
    "Q002",
    "Q003",
    "Q012",
    "Q013",
    "Q018",
    "Q026",
    "Q028",
    "Q039",
    "Q046",
    "Q050",
    "Q065",
    "Q069",
    "Q075",
    "Q080",
    "Q088",
    "Q089",
    "Q090",
    "Q091",
    "Q095",
    "Q107",
    "Q109",
    "Q115",
    "Q118",
)

REUSE_SOURCES: dict[str, Path] = {
    "Q001": Path(r"D:\SAGE125_Local_Runs\formal_5_evidence_remediation_20260822-004714\Q001"),
    "Q003": Path(r"D:\SAGE125_Local_Runs\formal_12_complete_20260822-140822\Q003"),
    "Q013": Path(r"D:\SAGE125_Local_Runs\formal_12_complete_20260822-140822\Q013"),
    "Q026": Path(r"D:\SAGE125_Local_Runs\formal_12_complete_20260822-140822\Q026"),
    "Q028": Path(r"D:\SAGE125_Local_Runs\formal_5_evidence_remediation_20260822-004714\Q028"),
    "Q046": Path(r"D:\SAGE125_Local_Runs\formal_12_complete_20260822-140822\Q046"),
    "Q050": Path(r"D:\SAGE125_Local_Runs\formal_5_evidence_remediation_20260822-004714\Q050"),
    "Q069": Path(r"D:\SAGE125_Local_Runs\formal_12_complete_20260822-140822\Q069"),
    "Q075": Path(r"D:\SAGE125_Local_Runs\formal_5_evidence_remediation_20260822-004714\Q075"),
    "Q088": Path(r"D:\SAGE125_Local_Runs\formal_12_complete_20260822-140822\Q088"),
    "Q089": Path(r"D:\SAGE125_Local_Runs\formal_12_complete_20260822-140822\Q089"),
    "Q091": Path(r"D:\SAGE125_Local_Runs\formal_12_complete_20260822-140822\Q091"),
    "Q095": Path(r"D:\SAGE125_Local_Runs\formal_12_complete_20260822-140822\Q095"),
    "Q107": Path(r"D:\SAGE125_Local_Runs\formal_5_evidence_remediation_20260822-004714\Q107"),
    "Q109": Path(r"D:\SAGE125_Local_Runs\formal_12_complete_20260822-140822\Q109"),
}

EXPECTED_LOCKS = {
    "catalog": "3dfe2cee452dda36211ab64d1581c39d0c9bf476401d2cd5bb1febfe5951a402",
    "domain_map": "d45bb65ce4d2620d2c91c7a7cb7eb44dd186be3b7ce7d71a1acbca03c92ed75a",
    "model": "84d00c01aeb6aef7b9202ee0de19e6192bb3f8e7a417eb156022ff6c4aac26d5",
    "prompt": "000bf988bf9abbb5392e0fc9f81081d5c6ec4743aa6f1092c0d289da26939896",
    "evidence_policy": "ead724149c65fc9ad5af4d611b5cdbdf69f033a8c7ebfea4294d92e66a14341e",
    "relevance_policy": "a7fc8983808794a751767ef139d89d5c385e78714a30cba393e01549f2a9da91",
    "gate_policy": "130b2ac0df6e5d89083ed7b0b840457b61055227fb3d08bf21accd5c8b99d156",
    "batch_policy": "6d921590fe703812862f831c992baac54a9ad5e461b50fc65f95815060fc5c0e",
    "output_contract": "12adede542cab7146359aca957bd5b4175d780c69623d35e2d6c481ca2527177",
}
LOCK_PATHS = {
    "catalog": ("docs/reproducibility/formal_125/catalog/questions_125.lock.json", "catalog_sha256"),
    "domain_map": ("docs/reproducibility/formal_125/catalog/domain_map.lock.json", "domain_map_sha256"),
    "model": ("docs/reproducibility/formal_125/formal_125_model.lock.json", "model_lock_sha256"),
    "prompt": ("docs/reproducibility/formal_125/formal_125_prompt.lock.v2.json", "prompt_lock_sha256"),
    "evidence_policy": (
        "docs/reproducibility/formal_125/formal_125_evidence_policy.lock.v3.json",
        "evidence_policy_sha256",
    ),
    "relevance_policy": (
        "docs/reproducibility/formal_125/formal_125_evidence_relevance_policy.lock.v1.json",
        "relevance_policy_sha256",
    ),
    "gate_policy": (
        "docs/reproducibility/formal_125/formal_125_gate_policy.lock.v3.json",
        "gate_policy_sha256",
    ),
    "batch_policy": (
        "docs/reproducibility/formal_125/formal_125_batch_policy.lock.v2.json",
        "batch_policy_sha256",
    ),
    "output_contract": (
        "docs/reproducibility/formal_125/formal_125_output_contract.lock.v2.json",
        "output_contract_sha256",
    ),
}

# Measured Formal 12 remaining-9: 9 questions, 99 calls, 629337 in, 118756 out.
MEASURED_CALLS_PER_QUESTION = 11
MEASURED_INPUT_PER_QUESTION = 69_926
MEASURED_OUTPUT_PER_QUESTION = 13_195
NOMINAL_CALLS = MEASURED_CALLS_PER_QUESTION * 110
P95_CALLS = NOMINAL_CALLS
WORST_CASE_CALLS = 20 * 110
NOMINAL_INPUT_TOKENS = MEASURED_INPUT_PER_QUESTION * 110
NOMINAL_OUTPUT_TOKENS = MEASURED_OUTPUT_PER_QUESTION * 110
WORST_CASE_INPUT_TOKENS = MEASURED_INPUT_PER_QUESTION * 20 * 110 // 11
WORST_CASE_OUTPUT_TOKENS = MEASURED_OUTPUT_PER_QUESTION * 20 * 110 // 11
AUTH_MAX_CALLS = WORST_CASE_CALLS
AUTH_MAX_INPUT = WORST_CASE_INPUT_TOKENS
AUTH_MAX_OUTPUT = WORST_CASE_OUTPUT_TOKENS

EVIDENCE_DISCOVERY_CONCURRENCY = 8
MODEL_QUESTION_CONCURRENCY_INITIAL = 3
MODEL_QUESTION_CONCURRENCY_MAX = 4
MODEL_QUESTION_CONCURRENCY_MIN = 1
MAX_RETRIES_PER_CALL = 1
EVIDENCE_PREP_MAX_MINUTES_PER_QUESTION = 8
MAX_FULLTEXT_FETCH_ATTEMPTS_PER_QUESTION = 12
STARTUP_SENTINEL_COUNT = 3
WAVE_SIZE = 10
LOCAL_CACHE_ROOTS = [
    Path(r"D:\SAGE125_Local_Evidence\formal_12_relevance_remediation_20260822-120516"),
    Path(r"D:\SAGE125_Local_Evidence\formal_5_evidence_remediation_20260822-004714"),
]

STOPWORDS = {
    "will",
    "the",
    "ever",
    "be",
    "what",
    "how",
    "why",
    "is",
    "are",
    "a",
    "an",
    "of",
    "to",
    "for",
    "and",
    "or",
    "in",
    "on",
    "at",
    "from",
    "with",
    "by",
    "as",
    "that",
    "this",
    "these",
    "those",
    "their",
    "there",
    "does",
    "do",
    "can",
    "could",
    "should",
    "would",
    "may",
    "might",
    "problem",
    "question",
    "so",
    "special",
    "make",
    "makes",
    "made",
    "into",
    "than",
    "then",
    "when",
    "where",
    "which",
    "who",
    "whom",
    "whose",
    "its",
    "it",
    "we",
    "our",
    "you",
    "your",
    "they",
    "them",
    "not",
    "no",
    "nor",
    "if",
    "but",
    "also",
    "very",
    "more",
    "most",
    "such",
    "any",
    "all",
    "each",
    "other",
    "only",
    "just",
    "even",
    "still",
    "over",
    "under",
    "between",
    "among",
    "about",
    "after",
    "before",
    "while",
    "during",
    "through",
    "without",
    "within",
    "because",
    "since",
    "used",
    "using",
    "use",
    "uses",
    "useful",
    "been",
    "being",
    "has",
    "have",
    "had",
    "was",
    "were",
    "did",
    "done",
    "get",
    "got",
    "given",
    "give",
    "there",
    "their",
    "them",
}

_QUEUE_LOCK = threading.Lock()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def official_question_ids() -> list[str]:
    return [f"Q{index:03d}" for index in range(1, 126)]


def remaining_case_ids(reused: tuple[str, ...] = REUSED_CASE_IDS) -> list[str]:
    reused_set = set(reused)
    remaining = [qid for qid in official_question_ids() if qid not in reused_set]
    return remaining


def verify_set_identity(
    reused: tuple[str, ...] = REUSED_CASE_IDS,
) -> dict[str, int]:
    all_ids = official_question_ids()
    remaining = remaining_case_ids(reused)
    reused_set = set(reused)
    remaining_set = set(remaining)
    if len(all_ids) != 125:
        raise ValueError("official catalog is not Q001-Q125")
    if len(reused_set) != 15 or len(reused) != 15:
        raise ValueError("reused set must be exactly 15 unique IDs")
    if len(remaining) != 110 or len(remaining_set) != 110:
        raise ValueError("remaining set must be exactly 110 unique IDs")
    if reused_set & remaining_set:
        raise ValueError("reused and remaining intersect")
    if reused_set | remaining_set != set(all_ids):
        raise ValueError("union is not Q001-Q125")
    return {
        "TOTAL": 125,
        "REUSED": 15,
        "REMAINING": 110,
        "INTERSECTION": 0,
        "UNION": 125,
    }


def assign_waves(remaining: list[str], wave_size: int = WAVE_SIZE) -> list[dict[str, Any]]:
    rows = []
    for index, question_id in enumerate(remaining):
        rows.append(
            {
                "question_id": question_id,
                "ordinal": int(question_id[1:]),
                "wave": index // wave_size + 1,
                "wave_index": index % wave_size,
                "wave_sentinel": index % wave_size == 0,
            }
        )
    return rows


def load_catalog(repo_root: Path) -> dict[str, Any]:
    path = repo_root / "docs/reproducibility/formal_125/catalog/questions_125.lock.json"
    return json.loads(path.read_text(encoding="utf-8"))


def catalog_item(catalog: Mapping[str, Any], question_id: str) -> dict[str, Any]:
    for item in catalog["questions"]:
        if item["question_id"] == question_id:
            return item
    raise KeyError(question_id)


def _clean_token(token: str) -> str:
    return re.sub(r"[^A-Za-z0-9\-–—]+", "", token).strip("-–—")


def _significant_terms(text: str) -> list[str]:
    terms: list[str] = []
    for match in re.finditer(r"[A-Za-z][A-Za-z0-9\-–—]{3,}", text):
        token = _clean_token(match.group(0))
        lowered = token.casefold()
        if not token or lowered in STOPWORDS or lowered in GENERIC_BANNED:
            continue
        if token not in terms:
            terms.append(token)
    for match in re.finditer(r'"([^"]{4,80})"', text):
        phrase = " ".join(match.group(1).split())
        if phrase.casefold() not in GENERIC_BANNED and phrase not in terms:
            terms.append(phrase)
    words = [_clean_token(part) for part in re.findall(r"[A-Za-z][A-Za-z0-9\-–—]+", text)]
    words = [word for word in words if word and word.casefold() not in STOPWORDS]
    for width in (3, 2):
        for index in range(0, max(0, len(words) - width + 1)):
            phrase = " ".join(words[index : index + width])
            if any(part.casefold() in GENERIC_BANNED for part in phrase.split()):
                continue
            if len(phrase) >= 8 and phrase not in terms:
                terms.append(phrase)
    return terms


def generic_template_from_catalog(item: Mapping[str, Any]) -> dict[str, Any]:
    title = str(item.get("original_title") or "")
    body = str(item.get("original_question_text") or title)
    terms = _significant_terms(title + " " + body)
    if not terms:
        raise ValueError(f"{item.get('question_id')} has no usable official anchors")
    objects = [[terms[0]]]
    if len(terms) > 1:
        objects.append([terms[1]])
    if len(terms) > 3:
        objects.append([terms[3]])
    phenom = [[terms[2]]] if len(terms) > 2 else [[terms[0]]]
    if len(terms) > 4:
        phenom.append([terms[4]])
    mech = [[terms[min(5, len(terms) - 1)]]]
    if len(terms) > 6:
        mech.append([terms[6]])
    queries = []
    for term in terms[:4]:
        if " " in term or "-" in term or "–" in term:
            queries.append(f'all:"{term}"')
        else:
            queries.append(f"all:{term}")
    if len(terms) >= 2:
        queries.append(f'all:"{terms[0]}" AND all:"{terms[1]}"')
    prohibited = [
        name
        for name in (
            "geodynamo",
            "YInMn",
            "Mars manufacturing",
            "diffraction limit",
            "WDBC",
        )
        if name.casefold() not in (title + " " + body).casefold()
    ]
    return {
        "domain_id": item.get("domain_id") or "unknown",
        "research_object_anchors": objects,
        "phenomenon_or_relation_anchors": phenom,
        "mechanism_or_constraint_anchors": mech,
        "method_anchors": [[terms[0]]],
        "required_anchor_groups": ["research_object", "phenomenon_or_mechanism"],
        "optional_synonyms": [],
        "prohibited_unrelated_topics": prohibited,
        "query_variants": queries[:5] or [f"all:{terms[0]}"],
        "evidence_roles": ["direct_core", "supporting_mechanism"],
    }


def ensure_relevance_template(item: Mapping[str, Any]) -> dict[str, Any]:
    question_id = str(item["question_id"])
    if question_id not in SPEC_TEMPLATES:
        SPEC_TEMPLATES[question_id] = generic_template_from_catalog(item)
    return SPEC_TEMPLATES[question_id]


def budget_from_measured_results() -> dict[str, Any]:
    return {
        "source": "formal_12_remaining_9_20260822-130025 plus Formal 5/12 measured 11 calls/question",
        "measured_questions": 9,
        "measured_calls": 99,
        "measured_input_tokens": 629337,
        "measured_output_tokens": 118756,
        "NOMINAL_CALLS": NOMINAL_CALLS,
        "P95_CALLS": P95_CALLS,
        "WORST_CASE_CALLS": WORST_CASE_CALLS,
        "NOMINAL_INPUT_TOKENS": NOMINAL_INPUT_TOKENS,
        "NOMINAL_OUTPUT_TOKENS": NOMINAL_OUTPUT_TOKENS,
        "WORST_CASE_INPUT_TOKENS": WORST_CASE_INPUT_TOKENS,
        "WORST_CASE_OUTPUT_TOKENS": WORST_CASE_OUTPUT_TOKENS,
        "authorized_max_calls": AUTH_MAX_CALLS,
        "authorized_max_input_tokens": AUTH_MAX_INPUT,
        "authorized_max_output_tokens": AUTH_MAX_OUTPUT,
        "covers_one_frozen_retry": True,
        "estimated_cost": "unknown",
    }


def verify_locks(repo_root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for name, (relative, key) in LOCK_PATHS.items():
        path = repo_root / relative
        payload = json.loads(path.read_text(encoding="utf-8"))
        declared = str(payload.get(key) or "")
        recomputed = sha256_canonical_json({item: value for item, value in payload.items() if item != key})
        if declared != recomputed:
            raise RuntimeError(f"HARD_STOP_2 lock hash mismatch in {relative}")
        if declared != EXPECTED_LOCKS[name]:
            raise RuntimeError(f"HARD_STOP_2 lock drift: {name}")
        hashes[name] = declared
    return hashes


def reuse_mode(question_id: str) -> str:
    if question_id == "Q095":
        return "REUSED_VERIFIED_GENUINE_PARTIAL"
    return "REUSED_VERIFIED_FORMAL_RESULT"


def verify_reused_question(question_id: str, source: Path) -> dict[str, Any]:
    missing = [name for name in REQUIRED_RESULT_FILES if not (source / name).is_file()]
    if missing:
        raise RuntimeError(f"{question_id} missing required files: {missing}")
    checksum_text = (source / "checksums.sha256").read_text(encoding="utf-8")
    for line in checksum_text.splitlines():
        if not line.strip():
            continue
        digest, name = line.split(None, 1)
        path = source / name.strip()
        if path.is_file() and sha256_file(path) != digest:
            raise RuntimeError(f"{question_id} checksum mismatch for {name}")
    manifest = json.loads((source / "package_manifest.json").read_text(encoding="utf-8"))
    status = str(manifest.get("status") or "")
    if question_id == "Q095":
        if status != "partial":
            raise RuntimeError("Q095 must remain genuine partial")
    elif status != "succeeded":
        raise RuntimeError(f"{question_id} expected succeeded, got {status}")
    pdf = source / "result.pdf"
    if pdf.stat().st_size < 100:
        raise RuntimeError(f"{question_id} PDF is empty")
    return {
        "question_id": question_id,
        "status": status,
        "execution_mode": reuse_mode(question_id),
        "source": str(source),
        "package_digest": sha256_file(source / "package_manifest.json"),
        "current_stage_provider_calls": 0,
    }


def copy_reused_question(question_id: str, destination_root: Path) -> dict[str, Any]:
    source = REUSE_SOURCES[question_id]
    report = verify_reused_question(question_id, source)
    dest = destination_root / question_id
    dest.mkdir(parents=True, exist_ok=True)
    for name in REQUIRED_RESULT_FILES:
        src = source / name
        target = dest / name
        if not target.exists():
            shutil.copy2(src, target)
        elif sha256_file(target) != sha256_file(src):
            raise RuntimeError(f"refusing to overwrite mutated reuse file {question_id}/{name}")
    lineage = {
        "question_id": question_id,
        "execution_mode": report["execution_mode"],
        "source_package": str(source),
        "source_package_digest": report["package_digest"],
        "scientific_producer_sha": SCIENTIFIC_PRODUCER_SHA,
        "current_stage_provider_calls": 0,
        "historical_ledger_reference": PROJECT_PROVIDER_CALLS_BEFORE,
        "copied_at": utc_now(),
        "byte_for_byte": True,
    }
    atomic_write_json(dest / "reuse_lineage.json", lineage)
    return report


def queue_path(output_root: Path) -> Path:
    return output_root / "runtime" / "queue.sqlite"


def connect_queue(output_root: Path) -> sqlite3.Connection:
    path = queue_path(output_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=60, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def reclaim_stale_claims(output_root: Path) -> None:
    if not queue_path(output_root).exists():
        return
    conn = connect_queue(output_root)
    with _QUEUE_LOCK:
        conn.execute(
            """
            UPDATE jobs
            SET evidence_status = 'pending', claim_token = NULL, claimed_at = NULL
            WHERE evidence_status = 'running'
            """
        )
        conn.execute(
            """
            UPDATE jobs
            SET model_status = 'queued', claim_token = NULL, claimed_at = NULL
            WHERE model_status = 'running' AND evidence_status = 'ready'
            """
        )
        conn.commit()
    conn.close()


def init_queue(output_root: Path, remaining: list[str], catalog: Mapping[str, Any]) -> None:
    conn = connect_queue(output_root)
    with _QUEUE_LOCK:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                question_id TEXT PRIMARY KEY,
                ordinal INTEGER NOT NULL,
                domain_id TEXT,
                wave INTEGER,
                wave_sentinel INTEGER DEFAULT 0,
                execution_mode TEXT,
                evidence_status TEXT NOT NULL,
                model_status TEXT NOT NULL,
                status TEXT,
                block_code TEXT,
                claim_token TEXT,
                claimed_at TEXT,
                completed_at TEXT,
                provider_calls INTEGER DEFAULT 0,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                error_signature TEXT,
                output_path TEXT,
                scientific_producer_sha TEXT,
                orchestrator_sha TEXT
            );
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT,
                kind TEXT,
                question_id TEXT,
                payload TEXT
            );
            CREATE TABLE IF NOT EXISTS budget (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                calls INTEGER DEFAULT 0,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                retries INTEGER DEFAULT 0,
                count_429 INTEGER DEFAULT 0,
                model_concurrency INTEGER DEFAULT 3
            );
            CREATE TABLE IF NOT EXISTS hard_stop (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                triggered INTEGER DEFAULT 0,
                code TEXT,
                reason TEXT,
                ts TEXT
            );
            """
        )
        conn.execute(
            "INSERT OR IGNORE INTO budget (id, model_concurrency) VALUES (1, ?)",
            (MODEL_QUESTION_CONCURRENCY_INITIAL,),
        )
        conn.execute("INSERT OR IGNORE INTO hard_stop (id, triggered) VALUES (1, 0)")
        waves = assign_waves(remaining)
        for row in waves:
            item = catalog_item(catalog, row["question_id"])
            conn.execute(
                """
                INSERT OR IGNORE INTO jobs (
                    question_id, ordinal, domain_id, wave, wave_sentinel,
                    execution_mode, evidence_status, model_status, status
                ) VALUES (?, ?, ?, ?, ?, 'NEW_ACTUAL', 'pending', 'pending', 'pending')
                """,
                (
                    row["question_id"],
                    row["ordinal"],
                    item.get("domain_id"),
                    row["wave"],
                    1 if row["wave_sentinel"] else 0,
                ),
            )
        conn.commit()
    conn.close()


def record_event(output_root: Path, kind: str, question_id: str | None, payload: Mapping[str, Any]) -> None:
    conn = connect_queue(output_root)
    with _QUEUE_LOCK:
        conn.execute(
            "INSERT INTO events (ts, kind, question_id, payload) VALUES (?, ?, ?, ?)",
            (utc_now(), kind, question_id, json.dumps(payload, ensure_ascii=False)),
        )
        conn.commit()
    conn.close()


def claim_evidence_job(output_root: Path, worker_id: str) -> str | None:
    conn = connect_queue(output_root)
    token = f"{worker_id}:{utc_now()}"
    with _QUEUE_LOCK:
        row = conn.execute(
            """
            SELECT question_id FROM jobs
            WHERE evidence_status = 'pending'
            ORDER BY ordinal
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            conn.close()
            return None
        question_id = row["question_id"]
        conn.execute(
            """
            UPDATE jobs
            SET evidence_status = 'running', claim_token = ?, claimed_at = ?
            WHERE question_id = ? AND evidence_status = 'pending'
            """,
            (token, utc_now(), question_id),
        )
        changed = conn.total_changes
        conn.commit()
    conn.close()
    return question_id if changed else None


def claim_model_job(output_root: Path, worker_id: str) -> str | None:
    conn = connect_queue(output_root)
    token = f"{worker_id}:{utc_now()}"
    with _QUEUE_LOCK:
        row = conn.execute(
            """
            SELECT question_id FROM jobs
            WHERE evidence_status = 'ready' AND model_status = 'queued'
            ORDER BY ordinal
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            conn.close()
            return None
        question_id = row["question_id"]
        conn.execute(
            """
            UPDATE jobs
            SET model_status = 'running', claim_token = ?, claimed_at = ?
            WHERE question_id = ? AND evidence_status = 'ready' AND model_status = 'queued'
            """,
            (token, utc_now(), question_id),
        )
        changed = conn.total_changes
        conn.commit()
    conn.close()
    return question_id if changed else None


def mark_evidence_ready(output_root: Path, question_id: str) -> None:
    conn = connect_queue(output_root)
    with _QUEUE_LOCK:
        conn.execute(
            """
            UPDATE jobs
            SET evidence_status = 'ready', model_status = 'queued', claim_token = NULL
            WHERE question_id = ?
            """,
            (question_id,),
        )
        conn.commit()
    conn.close()


def mark_evidence_blocked(output_root: Path, question_id: str, block_code: str) -> None:
    conn = connect_queue(output_root)
    with _QUEUE_LOCK:
        conn.execute(
            """
            UPDATE jobs
            SET evidence_status = 'blocked', model_status = 'blocked', status = 'blocked',
                block_code = ?, completed_at = ?, claim_token = NULL
            WHERE question_id = ?
            """,
            (block_code, utc_now(), question_id),
        )
        conn.commit()
    conn.close()


def mark_model_done(
    output_root: Path,
    question_id: str,
    status: str,
    calls: int,
    input_tokens: int,
    output_tokens: int,
    orchestrator_sha: str,
    error_signature: str | None = None,
) -> None:
    conn = connect_queue(output_root)
    with _QUEUE_LOCK:
        conn.execute(
            """
            UPDATE jobs
            SET model_status = ?, status = ?, provider_calls = ?, input_tokens = ?,
                output_tokens = ?, completed_at = ?, claim_token = NULL,
                scientific_producer_sha = ?, orchestrator_sha = ?, error_signature = ?
            WHERE question_id = ?
            """,
            (
                status,
                status,
                calls,
                input_tokens,
                output_tokens,
                utc_now(),
                SCIENTIFIC_PRODUCER_SHA,
                orchestrator_sha,
                error_signature,
                question_id,
            ),
        )
        conn.execute(
            """
            UPDATE budget SET calls = calls + ?, input_tokens = input_tokens + ?,
                output_tokens = output_tokens + ? WHERE id = 1
            """,
            (calls, input_tokens, output_tokens),
        )
        conn.commit()
    conn.close()


def add_retry(output_root: Path, is_429: bool = False) -> None:
    conn = connect_queue(output_root)
    with _QUEUE_LOCK:
        conn.execute(
            "UPDATE budget SET retries = retries + 1, count_429 = count_429 + ? WHERE id = 1",
            (1 if is_429 else 0,),
        )
        conn.commit()
    conn.close()


def budget_state(output_root: Path) -> dict[str, Any]:
    conn = connect_queue(output_root)
    row = conn.execute("SELECT * FROM budget WHERE id = 1").fetchone()
    hard = conn.execute("SELECT * FROM hard_stop WHERE id = 1").fetchone()
    conn.close()
    calls = int(row["calls"])
    ratio = max(
        calls / AUTH_MAX_CALLS,
        int(row["input_tokens"]) / AUTH_MAX_INPUT,
        int(row["output_tokens"]) / AUTH_MAX_OUTPUT,
    )
    return {
        "calls": calls,
        "input_tokens": int(row["input_tokens"]),
        "output_tokens": int(row["output_tokens"]),
        "retries": int(row["retries"]),
        "count_429": int(row["count_429"]),
        "model_concurrency": int(row["model_concurrency"]),
        "ratio": ratio,
        "hard_stop": bool(hard["triggered"]),
        "hard_stop_code": hard["code"],
        "hard_stop_reason": hard["reason"],
        "estimated_cost": "unknown",
    }


def set_model_concurrency(output_root: Path, value: int) -> int:
    bounded = max(MODEL_QUESTION_CONCURRENCY_MIN, min(MODEL_QUESTION_CONCURRENCY_MAX, value))
    conn = connect_queue(output_root)
    with _QUEUE_LOCK:
        conn.execute("UPDATE budget SET model_concurrency = ? WHERE id = 1", (bounded,))
        conn.commit()
    conn.close()
    return bounded


def trigger_hard_stop(output_root: Path, code: str, reason: str) -> None:
    conn = connect_queue(output_root)
    with _QUEUE_LOCK:
        conn.execute(
            "UPDATE hard_stop SET triggered = 1, code = ?, reason = ?, ts = ? WHERE id = 1",
            (code, reason, utc_now()),
        )
        conn.commit()
    conn.close()
    atomic_write_json(
        output_root / "HARD_STOP.json",
        {"HARD_STOP_TRIGGERED": True, "HARD_STOP_CODE": code, "HARD_STOP_REASON": reason, "ts": utc_now()},
    )


def hard_stop_triggered(output_root: Path) -> bool:
    conn = connect_queue(output_root)
    row = conn.execute("SELECT triggered FROM hard_stop WHERE id = 1").fetchone()
    conn.close()
    return bool(row and row["triggered"])


def job_counts(output_root: Path) -> dict[str, int]:
    conn = connect_queue(output_root)
    rows = conn.execute("SELECT evidence_status, model_status, status FROM jobs").fetchall()
    conn.close()
    counts = {
        "evidence_pending": 0,
        "evidence_running": 0,
        "evidence_ready": 0,
        "evidence_blocked": 0,
        "model_queued": 0,
        "model_running": 0,
        "succeeded": 0,
        "partial": 0,
        "failed": 0,
        "blocked": 0,
        "completed": 0,
    }
    for row in rows:
        ev = row["evidence_status"]
        mo = row["model_status"]
        st = row["status"]
        if ev == "pending":
            counts["evidence_pending"] += 1
        elif ev == "running":
            counts["evidence_running"] += 1
        elif ev == "ready":
            counts["evidence_ready"] += 1
        elif ev == "blocked":
            counts["evidence_blocked"] += 1
        if mo == "queued":
            counts["model_queued"] += 1
        elif mo == "running":
            counts["model_running"] += 1
        if st in {"succeeded", "partial", "failed", "blocked"}:
            counts[st] += 1
            counts["completed"] += 1
    return counts


def write_blocked_package(
    *,
    question_dir: Path,
    question_id: str,
    block_code: str,
    reason: str,
    orchestrator_sha: str,
    seed: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    question_dir.mkdir(parents=True, exist_ok=True)
    title = f"{question_id} blocked: {block_code}"
    md = "\n".join(
        [
            f"# {title}",
            "",
            "This official question did not receive a model generation attempt.",
            "",
            f"- block_code: `{block_code}`",
            f"- reason: {reason}",
            "- actual_execution: false",
            "- provider calls in this stage: 0",
            "",
            "Results were not fabricated. The nine-file package is a normative blocked shell.",
            "",
        ]
    )
    atomic_write_text(question_dir / "result.md", md)
    atomic_write_json(
        question_dir / "result.json",
        {
            "question_id": question_id,
            "status": "blocked",
            "block_code": block_code,
            "actual_execution": False,
            "generated_hypotheses": [],
            "paper_title": title,
            "scientific_producer_sha": SCIENTIFIC_PRODUCER_SHA,
            "orchestrator_sha": orchestrator_sha,
        },
    )
    atomic_write_json(question_dir / "evidence_cards.json", (seed or {}).get("eligible_cards") or [])
    atomic_write_json(
        question_dir / "agent_trace.json",
        [{"event": "blocked", "block_code": block_code, "reason": reason, "ts": utc_now()}],
    )
    atomic_write_json(
        question_dir / "validation.json",
        {
            "question_id": question_id,
            "p0_count": 0,
            "p1_count": 0,
            "blocked": True,
            "block_code": block_code,
            "actual_execution": False,
            "estimated_cost": "unknown",
        },
    )
    atomic_write_json(
        question_dir / "provider_audit.json",
        {
            "question_id": question_id,
            "provider": "bailian",
            "records": [],
            "summary": {"calls": 0, "input_tokens": 0, "output_tokens": 0},
            "estimated_cost": "unknown",
        },
    )
    export_markdown_to_pdf(question_dir / "result.md", question_dir / "result.pdf")
    hashed_names = [name for name in REQUIRED_RESULT_FILES if name != "checksums.sha256"]
    files = []
    checksum_lines = []
    for name in hashed_names:
        path = question_dir / name
        digest = sha256_file(path) if path.is_file() else None
        files.append(
            {
                "name": name,
                "present": path.is_file() and path.stat().st_size > 0,
                "size_bytes": path.stat().st_size if path.is_file() else 0,
                "sha256": digest,
            }
        )
        if digest:
            checksum_lines.append(f"{digest}  {name}")
    atomic_write_json(
        question_dir / "package_manifest.json",
        {
            "question_id": question_id,
            "status": "blocked",
            "block_code": block_code,
            "files": files,
            "provider_calls": 0,
            "real_provider_calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "estimated_cost": "unknown",
            "scientific_producer_sha": SCIENTIFIC_PRODUCER_SHA,
            "orchestrator_sha": orchestrator_sha,
            "packaged_at": utc_now(),
        },
    )
    atomic_write_text(question_dir / "checksums.sha256", "\n".join(checksum_lines) + "\n")
    files.append(
        {
            "name": "checksums.sha256",
            "present": True,
            "size_bytes": (question_dir / "checksums.sha256").stat().st_size,
            "sha256": sha256_file(question_dir / "checksums.sha256"),
        }
    )
    return {"question_id": question_id, "status": "blocked", "block_code": block_code, "calls": 0}


def build_authorization_payload(
    *,
    remaining: list[str],
    output_root: Path,
    locks: Mapping[str, str],
) -> dict[str, Any]:
    payload = {
        "authorization_id": f"formal125-fast-{STAMP}",
        "authorized_by_role": "captain",
        "authorized_case_ids": remaining,
        "provider": "bailian",
        "model_lock_hash": locks["model"],
        "prompt_lock_hash": locks["prompt"],
        "schema_lock_hash": locks["output_contract"],
        "catalog_hash": locks["catalog"],
        "max_total_provider_calls": AUTH_MAX_CALLS,
        "max_retries": MAX_RETRIES_PER_CALL,
        "max_total_input_tokens": AUTH_MAX_INPUT,
        "max_total_output_tokens": AUTH_MAX_OUTPUT,
        "max_concurrency": MODEL_QUESTION_CONCURRENCY_MAX,
        "output_root": str(output_root),
        "expires_at": "2026-09-30T00:00:00+00:00",
    }
    payload["authorization_hash"] = compute_authorization_hash(payload)
    return payload


def write_authorization_noclobber(path: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, path)
    return dict(payload)


def progress_payload(
    *,
    output_root: Path,
    reused_reports: list[Mapping[str, Any]],
    api_url: str,
    ui_url: str,
    heartbeat: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    counts = job_counts(output_root) if queue_path(output_root).exists() else {}
    budget = budget_state(output_root) if queue_path(output_root).exists() else {}
    succeeded = int(counts.get("succeeded") or 0) + 14
    partial = int(counts.get("partial") or 0) + 1
    failed = int(counts.get("failed") or 0)
    blocked = int(counts.get("blocked") or 0)
    completed = int(counts.get("completed") or 0) + 15
    return {
        "total": 125,
        "completed": completed,
        "running": int(counts.get("model_running") or 0) + int(counts.get("evidence_running") or 0),
        "queued": int(counts.get("model_queued") or 0) + int(counts.get("evidence_pending") or 0),
        "succeeded": succeeded,
        "partial": partial,
        "failed": failed,
        "blocked": blocked,
        "evidence_pending": counts.get("evidence_pending"),
        "evidence_ready": counts.get("evidence_ready"),
        "evidence_blocked": counts.get("evidence_blocked"),
        "current_concurrency": budget.get("model_concurrency"),
        "provider_calls": budget.get("calls"),
        "input_tokens": budget.get("input_tokens"),
        "output_tokens": budget.get("output_tokens"),
        "count_429": budget.get("count_429"),
        "retries": budget.get("retries"),
        "reused_count": 15,
        "FINAL_SUBMISSION_READY": False,
        "api_url": api_url,
        "ui_url": ui_url,
        "heartbeat": heartbeat or {},
        "estimated_cost": "unknown",
        "secrets_included": False,
    }


SECRET_PATTERNS = (
    re.compile(r"(?i)(?:api[_-]?key|authorization|bearer|password|secret)\s*[:=]\s*\S+"),
    re.compile(r"(?i)sk-[A-Za-z0-9]{8,}"),
    re.compile(r"(?i)workspace_id\s*[:=]\s*\S+"),
)


def scan_text_for_secrets(text: str) -> int:
    return sum(1 for pattern in SECRET_PATTERNS if pattern.search(text or ""))


def write_review_packet(question_dir: Path, review_dir: Path) -> None:
    review_dir.mkdir(parents=True, exist_ok=True)
    result = json.loads((question_dir / "result.json").read_text(encoding="utf-8")) if (question_dir / "result.json").is_file() else {}
    evidence = json.loads((question_dir / "evidence_cards.json").read_text(encoding="utf-8")) if (question_dir / "evidence_cards.json").is_file() else []
    validation = json.loads((question_dir / "validation.json").read_text(encoding="utf-8")) if (question_dir / "validation.json").is_file() else {}
    audit = json.loads((question_dir / "provider_audit.json").read_text(encoding="utf-8")) if (question_dir / "provider_audit.json").is_file() else {}
    manifest = json.loads((question_dir / "package_manifest.json").read_text(encoding="utf-8")) if (question_dir / "package_manifest.json").is_file() else {}
    atomic_write_json(
        review_dir / "review_input.json",
        {"question_id": question_dir.name, "result_path": str(question_dir), "status": manifest.get("status")},
    )
    atomic_write_json(
        review_dir / "result_summary.json",
        {
            "question_id": question_dir.name,
            "status": manifest.get("status"),
            "paper_title": result.get("paper_title") or result.get("title"),
            "actual_execution": result.get("actual_execution", False),
        },
    )
    atomic_write_json(
        review_dir / "evidence_summary.json",
        {
            "question_id": question_dir.name,
            "evidence_count": len(evidence) if isinstance(evidence, list) else 0,
            "evidence_ids": [item.get("evidence_id") for item in evidence] if isinstance(evidence, list) else [],
        },
    )
    links = []
    for hyp in result.get("generated_hypotheses") or result.get("hypotheses") or []:
        if isinstance(hyp, dict):
            links.append(
                {
                    "claim": hyp.get("hypothesis") or hyp.get("statement"),
                    "supporting_evidence_ids": hyp.get("supporting_evidence_ids") or [],
                }
            )
    atomic_write_json(review_dir / "claim_evidence_links.json", {"links": links})
    atomic_write_json(review_dir / "validation_summary.json", validation)
    atomic_write_json(
        review_dir / "provider_audit_summary.json",
        {
            "calls": (audit.get("summary") or {}).get("calls") or manifest.get("provider_calls") or 0,
            "estimated_cost": "unknown",
        },
    )
    atomic_write_json(review_dir / "similarity_findings.json", validation.get("similarity") or {})
    atomic_write_json(
        review_dir / "review_form.json",
        {"question_id": question_dir.name, "reviewed": False, "decision": None},
    )


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
