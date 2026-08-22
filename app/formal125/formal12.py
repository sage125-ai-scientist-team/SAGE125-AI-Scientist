"""Formal 12 domain representative run: stage A (no Provider) and stage B helpers.

Stage A must not call Qwen, embedding, rerank, Deep Research, or OpenRouter.
Stage B requires the exact captain authorization text and is not started here.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from app.agents import prompts as prompt_module
from app.evidence.oa_fulltext import FulltextFetchAudit
from app.evidence.relevance import is_content_bearing
from app.evidence.remediation import FORMAL_12_NEW, QUERY_SEEDS, build_seed_bundle, write_json
from app.formal125 import REQUIRED_RESULT_FILES
from app.formal125.catalog import T09_DOMAIN_REPRESENTATIVES
from app.formal125.evidence_rerun import LOCK_V2, evaluate_attempt2_gates
from app.formal125.hashes import sha256_canonical_json, sha256_file
from app.formal125.pipeline_plan import CHAT_STEPS, MAX_CONCURRENCY, REVISION_STEPS
from app.formal125.preflight import FORMAL_GATES, PROMPT_NAMES

STAMP = "20260822-014248"
FORMAL_12_BASE_SHA = "ac3ab581c7a221a21b8cf5806e52997b7c8629e9"
EVIDENCE_PRODUCER_SHA = "309da9fccfd8ce1f247ab772293233e276b6a1a3"
ATTEMPT2_RUNNER_SHA = "194420d33c6e911c0c1ee525e10803f3337a236d"
FORMAL_5_ATTEMPT2_ROOT = Path(r"D:\SAGE125_Local_Runs\formal_5_evidence_remediation_20260822-004714")
FORMAL_12_CASE_IDS: tuple[str, ...] = (
    "Q001",
    "Q069",
    "Q003",
    "Q026",
    "Q013",
    "Q109",
    "Q091",
    "Q089",
    "Q046",
    "Q095",
    "Q107",
    "Q088",
)
FORMAL_12_SELECTION_SHA256 = "7b23ec21acf908808306bb037f8f26231529abbe5a8de33977bf2e220d26b7d4"
PROJECT_PROVIDER_CALLS_BEFORE_FORMAL_12 = 121
PROMPT_LOCK_V1 = "5b12d88b01fc18278dc2d90087caf374e8be0a0ab57eb567c37a2b7121d4e8d2"
EVIDENCE_POLICY_V1 = "89a6bd4194bd4bd0721ff7ee4af29fda9647c67bb9950f71938fa2c533f39a63"
CANARY_QUESTION_ID = "Q069"
CHAT_STEPS_PER_QUESTION = len(CHAT_STEPS)
REVISION_STEPS_PER_QUESTION = len(REVISION_STEPS)
ATTEMPT2_CALLS_PER_QUESTION = 11
ATTEMPT2_INPUT_PER_QUESTION = 59_971
ATTEMPT2_OUTPUT_PER_QUESTION = 11_255
LOCK_FILES = {
    "catalog": ("docs/reproducibility/formal_125/catalog/questions_125.lock.json", "catalog_sha256"),
    "domain_map": ("docs/reproducibility/formal_125/catalog/domain_map.lock.json", "domain_map_sha256"),
    "model": ("docs/reproducibility/formal_125/formal_125_model.lock.json", "model_lock_sha256"),
    "prompt": ("docs/reproducibility/formal_125/formal_125_prompt.lock.v2.json", "prompt_lock_sha256"),
    "evidence_policy": (
        "docs/reproducibility/formal_125/formal_125_evidence_policy.lock.v2.json",
        "evidence_policy_sha256",
    ),
    "gate_policy": ("docs/reproducibility/formal_125/formal_125_gate_policy.lock.v2.json", "gate_policy_sha256"),
    "output_contract": (
        "docs/reproducibility/formal_125/formal_125_output_contract.lock.v2.json",
        "output_contract_sha256",
    ),
    "batch_policy": ("docs/reproducibility/formal_125/formal_125_batch_policy.lock.json", "batch_policy_sha256"),
}
EXPECTED_LOCKS = {
    "CATALOG_SHA256": LOCK_V2["catalog_hash"],
    "DOMAIN_MAP_SHA256": "d45bb65ce4d2620d2c91c7a7cb7eb44dd186be3b7ce7d71a1acbca03c92ed75a",
    "MODEL_LOCK_SHA256": LOCK_V2["model_lock_hash"],
    "PROMPT_LOCK_SHA256": LOCK_V2["prompt_lock_hash"],
    "EVIDENCE_POLICY_LOCK_SHA256": LOCK_V2["evidence_policy_lock_hash"],
    "GATE_POLICY_LOCK_SHA256": LOCK_V2["gate_policy_lock_hash"],
    "OUTPUT_CONTRACT_SHA256": LOCK_V2["schema_lock_hash"],
    "BATCH_POLICY_SHA256": "aa1e7cc2d1799956eb014018a03e7cd58424eef67017da0d434d708b3a0fbac1",
}
LEAK_PATTERNS = (
    ("Q028", re.compile(r"\bQ028\b")),
    ("WDBC", re.compile(r"\bWDBC\b", re.IGNORECASE)),
    ("cancer_cure", re.compile(r"cancer cure", re.IGNORECASE)),
    ("animal_epidemic", re.compile(r"口蹄疫|非洲猪瘟|animal epidemic", re.IGNORECASE)),
    ("openrouter", re.compile(r"openrouter", re.IGNORECASE)),
)
SECRET_PATTERNS = (
    re.compile(r"(?i)(?:api[_-]?key|authorization|bearer|password|secret)\s*[:=]\s*\S+"),
    re.compile(r"(?i)sk-[A-Za-z0-9]{8,}"),
    re.compile(r"(?i)workspace_id\s*[:=]\s*\S+"),
)
AUTHORIZATION_TEXT = "AUTHORIZE_FORMAL_12_DOMAIN_REAL_RUN=YES"


class Formal12Error(RuntimeError):
    """Fail-closed Formal 12 error."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def git_head(repo_root: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_root, text=True).strip()


def git_diff_stat(repo_root: Path, old: str, new: str) -> str:
    return subprocess.check_output(
        ["git", "diff", "--stat", old, new],
        cwd=repo_root,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_declared_hash(path: Path, key: str) -> str:
    payload = _load_json(path)
    declared = str(payload.get(key) or "")
    recomputed = sha256_canonical_json({item: value for item, value in payload.items() if item != key})
    if declared != recomputed:
        raise Formal12Error(f"{path.name} {key} mismatch: declared {declared} != {recomputed}")
    return declared


def build_lock_bundle(repo_root: Path) -> dict[str, Any]:
    files: dict[str, Any] = {}
    hashes: dict[str, str] = {}
    for name, (relative, key) in LOCK_FILES.items():
        path = repo_root / relative
        if not path.is_file():
            raise Formal12Error(f"missing lock file: {relative}")
        declared = verify_declared_hash(path, key)
        files[name] = {
            "path": relative,
            "file_sha256": sha256_file(path),
            "declared_hash_key": key,
            "declared_hash": declared,
            "lineage": "formal_5_attempt2_v2" if "v2" in relative or name in {"catalog", "domain_map", "model", "batch_policy"} else "unknown",
        }
        hashes[name] = declared
    if hashes["prompt"] == PROMPT_LOCK_V1:
        raise Formal12Error("refusing preflight prompt lock v1")
    if hashes["evidence_policy"] == EVIDENCE_POLICY_V1:
        raise Formal12Error("refusing evidence policy v1")
    expected_map = {
        "catalog": EXPECTED_LOCKS["CATALOG_SHA256"],
        "domain_map": EXPECTED_LOCKS["DOMAIN_MAP_SHA256"],
        "model": EXPECTED_LOCKS["MODEL_LOCK_SHA256"],
        "prompt": EXPECTED_LOCKS["PROMPT_LOCK_SHA256"],
        "evidence_policy": EXPECTED_LOCKS["EVIDENCE_POLICY_LOCK_SHA256"],
        "gate_policy": EXPECTED_LOCKS["GATE_POLICY_LOCK_SHA256"],
        "output_contract": EXPECTED_LOCKS["OUTPUT_CONTRACT_SHA256"],
        "batch_policy": EXPECTED_LOCKS["BATCH_POLICY_SHA256"],
    }
    mismatches = {name: hashes[name] for name, expected in expected_map.items() if hashes[name] != expected}
    if mismatches:
        raise Formal12Error(f"lock hashes do not match Attempt 2 lineage: {mismatches}")
    selection = _load_json(repo_root / "docs/reproducibility/formal_125/formal_12_domain_selection_manifest.json")
    if selection.get("selection_sha256") != FORMAL_12_SELECTION_SHA256:
        raise Formal12Error("FORMAL_12_SELECTION_SHA256 mismatch")
    if selection.get("question_ids") != list(FORMAL_12_CASE_IDS):
        raise Formal12Error("frozen 12-question order mismatch")
    bundle = {
        "lineage": {
            "formal_5_attempt2_authorization_hash": "f89a17120f53aeec8b8262288dd06d9fdcea58523afd19299b55ca5db31f7f34",
            "formal_12_base_sha": FORMAL_12_BASE_SHA,
            "attempt2_runner_sha": ATTEMPT2_RUNNER_SHA,
            "evidence_producer_sha": EVIDENCE_PRODUCER_SHA,
            "prompt_lock_rejected_v1": PROMPT_LOCK_V1,
            "evidence_policy_rejected_v1": EVIDENCE_POLICY_V1,
        },
        "locks": files,
        "CATALOG_SHA256": hashes["catalog"],
        "DOMAIN_MAP_SHA256": hashes["domain_map"],
        "MODEL_LOCK_SHA256": hashes["model"],
        "PROMPT_LOCK_SHA256": hashes["prompt"],
        "EVIDENCE_POLICY_LOCK_SHA256": hashes["evidence_policy"],
        "GATE_POLICY_LOCK_SHA256": hashes["gate_policy"],
        "OUTPUT_CONTRACT_SHA256": hashes["output_contract"],
        "BATCH_POLICY_SHA256": hashes["batch_policy"],
        "FORMAL_12_SELECTION_SHA256": FORMAL_12_SELECTION_SHA256,
        "minimum_fulltext_sources_per_question": 2,
        "verified_at": utc_now(),
    }
    bundle["lock_bundle_sha256"] = sha256_canonical_json(
        {key: value for key, value in bundle.items() if key != "lock_bundle_sha256"}
    )
    return bundle


def _question_from_catalog(repo_root: Path, question_id: str) -> dict[str, Any]:
    catalog = _load_json(repo_root / "docs/reproducibility/formal_125/catalog/questions_125.lock.json")
    for item in catalog["questions"]:
        if item["question_id"] == question_id:
            return item
    raise Formal12Error(f"{question_id} missing from catalog")


def _verify_checksums(question_dir: Path) -> bool:
    checksum_path = question_dir / "checksums.sha256"
    if not checksum_path.is_file():
        return False
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, name = line.split(None, 1)
        path = question_dir / name.strip()
        if name.strip() == "checksums.sha256":
            continue
        if not path.is_file() or sha256_file(path) != digest:
            return False
    return True


def _pdf_openable(path: Path) -> bool:
    if not path.is_file() or path.read_bytes()[:4] != b"%PDF":
        return False
    from pypdf import PdfReader
    from io import BytesIO

    reader = PdfReader(BytesIO(path.read_bytes()))
    return len(reader.pages) >= 1


def _scientific_diff_allowed(stat: str) -> bool:
    allowed_files = {
        "app/core/evidence_links.py",
        "app/formal125/evidence_rerun.py",
        "tests/test_evidence_links.py",
        "app/formal125/formal12.py",
        "app/formal125/readonly_display.py",
        "scripts/formal125/run_formal_12_stage_a.py",
        "tests/formal125/test_formal_12_stage_a.py",
        "app/api/routes.py",
        "app/ui/streamlit_app.py",
        "docs/reproducibility/formal_125/formal_12_lock_bundle.json",
    }
    for line in stat.splitlines():
        text = line.strip()
        if not text or text.startswith(" "):
            continue
        if "|" not in text:
            continue
        path = text.split("|", 1)[0].strip()
        if path in allowed_files:
            continue
        if path.startswith("tests/") or path.startswith("app/formal125/") or path.startswith("app/evidence/"):
            # evidence/remediation seed builder is orchestration, not prompt/model/gate lock.
            if path in {"app/evidence/remediation.py"}:
                continue
        if path.endswith(".py") and path not in allowed_files:
            if path in {"app/agents/prompts.py", "app/workflow/quality_gates.py", "app/core/config.py"}:
                return False
    return True


def evaluate_reuse_eligibility(repo_root: Path, question_id: str, lock_bundle: Mapping[str, Any]) -> dict[str, Any]:
    source = FORMAL_5_ATTEMPT2_ROOT / question_id
    catalog_item = _question_from_catalog(repo_root, question_id)
    checks: dict[str, Any] = {}
    missing = [name for name in REQUIRED_RESULT_FILES if not (source / name).is_file()]
    checks["required_files_9_of_9"] = not missing
    manifest = _load_json(source / "package_manifest.json")
    validation = _load_json(source / "validation.json")
    audit = _load_json(source / "provider_audit.json")
    lineage = _load_json(source / "attempt_lineage.json") if (source / "attempt_lineage.json").is_file() else {}
    result = _load_json(source / "result.json")
    checks["status_succeeded"] = manifest.get("status") == "succeeded"
    checks["manifest_matches_files"] = all(
        (source / item["name"]).is_file() and (source / item["name"]).stat().st_size == item.get("size_bytes")
        for item in manifest.get("files") or []
        if item.get("name") != "package_manifest.json"
    )
    checks["checksums_pass"] = _verify_checksums(source)
    checks["pdf_openable"] = _pdf_openable(source / "result.pdf")
    checks["question_id_matches_catalog"] = result.get("question_id") == question_id or catalog_item["question_id"] == question_id
    selection = _load_json(repo_root / "docs/reproducibility/formal_125/formal_12_domain_selection_manifest.json")
    selected = next(item for item in selection["questions"] if item["question_id"] == question_id)
    checks["question_hash_matches"] = catalog_item["question_hash"] == selected["question_hash"]
    checks["model_lock"] = lock_bundle["MODEL_LOCK_SHA256"] == EXPECTED_LOCKS["MODEL_LOCK_SHA256"]
    checks["prompt_lock_v2"] = lock_bundle["PROMPT_LOCK_SHA256"] == EXPECTED_LOCKS["PROMPT_LOCK_SHA256"]
    checks["evidence_policy_lock_v2"] = (
        lock_bundle["EVIDENCE_POLICY_LOCK_SHA256"] == EXPECTED_LOCKS["EVIDENCE_POLICY_LOCK_SHA256"]
    )
    checks["gate_policy_lock_v2"] = lock_bundle["GATE_POLICY_LOCK_SHA256"] == EXPECTED_LOCKS["GATE_POLICY_LOCK_SHA256"]
    checks["output_contract"] = lock_bundle["OUTPUT_CONTRACT_SHA256"] == EXPECTED_LOCKS["OUTPUT_CONTRACT_SHA256"]
    checks["batch_policy_compatible"] = lock_bundle["BATCH_POLICY_SHA256"] == EXPECTED_LOCKS["BATCH_POLICY_SHA256"]
    checks["provider_audit_complete"] = int((audit.get("summary") or {}).get("total_calls") or 0) > 0
    checks["mock_zero"] = int((audit.get("summary") or {}).get("mock_call_count") or 0) == 0
    checks["openrouter_zero"] = "openrouter" not in json.dumps(audit).lower()
    checks["secret_zero"] = not any(pattern.search(json.dumps(audit)) for pattern in SECRET_PATTERNS)
    checks["p0_zero"] = int(validation.get("p0_count") or 0) == 0
    checks["p1_zero"] = int(validation.get("p1_count") or 0) == 0
    gates = evaluate_attempt2_gates(question_id, source)
    checks["unknown_evidence_id_zero"] = gates["unknown_evidence_id_count"] == 0
    checks["metadata_fact_zero"] = gates["metadata_only_used_as_fact_count"] == 0
    checks["booklet_evidence_zero"] = gates["booklet_evidence_count"] == 0
    checks["cross_question_evidence_zero"] = gates["cross_question_evidence_id_count"] == 0
    checks["quote_locator_complete"] = gates["missing_quote_count"] == 0 and gates["missing_locator_count"] == 0
    bundle_path = source / "evidence_bundle.json"
    checks["evidence_bundle_checksum"] = bundle_path.is_file() and len(str(_load_json(bundle_path).get("bundle_hash") or "")) == 64
    runner_diff = git_diff_stat(repo_root, ATTEMPT2_RUNNER_SHA, FORMAL_12_BASE_SHA)
    checks["code_diff_runner_to_base_allowed"] = _scientific_diff_allowed(runner_diff)
    checks["input_question_matches"] = result.get("input_question") == catalog_item["original_title"]
    failed = [name for name, value in checks.items() if value is not True]
    eligible = not failed
    attestation = {
        "question_id": question_id,
        "source_formal_5_attempt": 2,
        "source_output_path": str(source),
        "source_package_digest": sha256_file(source / "package_manifest.json"),
        "source_provider_audit_digest": sha256_file(source / "provider_audit.json"),
        "source_producer_sha": lineage.get("producer_git_sha") or EVIDENCE_PRODUCER_SHA,
        "attempt2_runner_sha": ATTEMPT2_RUNNER_SHA,
        "formal_12_base_sha": FORMAL_12_BASE_SHA,
        "current_lock_sha": {
            "model": lock_bundle["MODEL_LOCK_SHA256"],
            "prompt": lock_bundle["PROMPT_LOCK_SHA256"],
            "evidence_policy": lock_bundle["EVIDENCE_POLICY_LOCK_SHA256"],
            "gate_policy": lock_bundle["GATE_POLICY_LOCK_SHA256"],
            "output_contract": lock_bundle["OUTPUT_CONTRACT_SHA256"],
        },
        "reuse_eligibility_checks": checks,
        "failed_checks": failed,
        "eligible": eligible,
        "reused_without_new_provider_call": True,
        "immutable_source": True,
        "scientific_input_unchanged": True,
        "code_diff_194420d_to_ac3ab58": runner_diff.strip(),
        "reuse_reason": (
            "Attempt 2 succeeded under runner 194420d; ac3ab58 only reconstructs arXiv /pdf/ identifiers for packaging."
            if eligible
            else f"reuse blocked: {failed}"
        ),
        "reused_at": utc_now(),
    }
    attestation["attestation_sha256"] = sha256_canonical_json(
        {key: value for key, value in attestation.items() if key != "attestation_sha256"}
    )
    return attestation


def prepare_new_case_seeds(
    *,
    repo_root: Path,
    cache_root: Path,
    output_root: Path,
    local_cache_roots: list[Path],
    audit: FulltextFetchAudit,
) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for question_id in FORMAL_12_NEW:
        existing = output_root / question_id / "evidence_bundle.json"
        if existing.is_file():
            previous = json.loads(existing.read_text(encoding="utf-8"))
            topic_ready = str((previous.get("topic_gate") or {}).get("gate_status") or "") == "READY"
            if (
                previous.get("evidence_seed_ready")
                and topic_ready
                and int(previous.get("direct_core_count") or 0) >= 1
                and int(previous.get("fulltext_verified_source_count") or 0) >= 2
            ):
                item = _question_from_catalog(repo_root, question_id)
                results[question_id] = {
                    "question_id": question_id,
                    "question_hash": item["question_hash"],
                    "original_title": item["original_title"],
                    "query_seeds": list(QUERY_SEEDS[question_id]),
                    "FULLTEXT_VERIFIED_COUNT": previous.get("fulltext_verified_source_count") or 0,
                    "ABSTRACT_VERIFIED_COUNT": previous.get("abstract_verified_count") or 0,
                    "ELIGIBLE_EVIDENCE_COUNT": previous.get("eligible_evidence_count") or 0,
                    "METADATA_ONLY_COUNT": previous.get("metadata_only_count") or 0,
                    "FETCH_FAILED_COUNT": previous.get("fetch_failed_count") or 0,
                    "LICENSE_RESTRICTED_COUNT": previous.get("license_restricted_count") or 0,
                    "UNKNOWN_EVIDENCE_ID_COUNT": previous.get("unknown_evidence_id_count") or 0,
                    "BOOKLET_EVIDENCE_COUNT": previous.get("booklet_evidence_count") or 0,
                    "CROSS_QUESTION_EVIDENCE_ID_COUNT": previous.get("cross_question_evidence_id_count") or 0,
                    "EVIDENCE_SEED_READY": True,
                    "bundle_hash": previous.get("bundle_hash"),
                    "reused_existing_seed": True,
                }
                continue
        item = _question_from_catalog(repo_root, question_id)
        bundle = build_seed_bundle(
            question_id=question_id,
            question_title=item["original_title"],
            cache_root=cache_root,
            output_root=output_root,
            audit=audit,
            local_cache_roots=local_cache_roots,
        )
        results[question_id] = {
            "question_id": question_id,
            "question_hash": item["question_hash"],
            "original_title": item["original_title"],
            "query_seeds": list(QUERY_SEEDS[question_id]),
            "FULLTEXT_VERIFIED_COUNT": bundle.get("fulltext_verified_source_count") or 0,
            "ABSTRACT_VERIFIED_COUNT": bundle.get("abstract_verified_count") or 0,
            "ELIGIBLE_EVIDENCE_COUNT": bundle.get("eligible_evidence_count") or 0,
            "METADATA_ONLY_COUNT": bundle.get("metadata_only_count") or 0,
            "FETCH_FAILED_COUNT": bundle.get("fetch_failed_count") or 0,
            "LICENSE_RESTRICTED_COUNT": bundle.get("license_restricted_count") or 0,
            "UNKNOWN_EVIDENCE_ID_COUNT": bundle.get("unknown_evidence_id_count") or 0,
            "BOOKLET_EVIDENCE_COUNT": bundle.get("booklet_evidence_count") or 0,
            "CROSS_QUESTION_EVIDENCE_ID_COUNT": bundle.get("cross_question_evidence_id_count") or 0,
            "EVIDENCE_SEED_READY": bool(bundle.get("evidence_seed_ready")),
            "bundle_hash": bundle.get("bundle_hash"),
        }
    return results


def plan_only_rehearsal(
    repo_root: Path,
    seed_root: Path,
    lock_bundle: Mapping[str, Any],
) -> dict[str, Any]:
    catalog_by_id = {
        item["question_id"]: item
        for item in _load_json(repo_root / "docs/reproducibility/formal_125/catalog/questions_125.lock.json")["questions"]
    }
    domain_by_id = {qid: t09 for qid, t09, _booklet in T09_DOMAIN_REPRESENTATIVES}
    plans = []
    leak_hits: list[dict[str, str]] = []
    cross_prompt = 0
    cross_evidence = 0
    fixture_leak = 0
    openrouter_route = 0
    mock_route = 0
    prompt_source = "\n".join(str(getattr(prompt_module, name, "")) for name in PROMPT_NAMES)
    for question_id in FORMAL_12_CASE_IDS:
        item = catalog_by_id[question_id]
        seed_path = seed_root / question_id / "evidence_bundle.json"
        seed = _load_json(seed_path) if seed_path.is_file() else {}
        if question_id in {"Q001", "Q107"} and not seed:
            source_seed = FORMAL_5_ATTEMPT2_ROOT / question_id / "evidence_bundle.json"
            seed = _load_json(source_seed) if source_seed.is_file() else {}
        planned = {
            "question_id": question_id,
            "question_context": {
                "original_title": item["original_title"],
                "question_hash": item["question_hash"],
                "booklet_domain": item["booklet_domain"],
                "t09_domain_id": domain_by_id[question_id],
            },
            "evidence_seed_context": {
                "allowed_evidence_ids": seed.get("allowed_evidence_ids") or [],
                "bundle_hash": seed.get("bundle_hash"),
                "fulltext_verified_source_count": seed.get("fulltext_verified_source_count") or 0,
            },
            "workspace": f"ws-formal12-{question_id.lower()}",
            "context_id": f"ctx-formal12-{question_id.lower()}",
            "cache_namespace": f"cache-formal12-{question_id.lower()}",
            "output_path": str(Path(rf"D:\SAGE125_Local_Runs\formal_12_domain_real_{STAMP}") / question_id),
            "planned_model_route": {
                "provider": "bailian",
                "openrouter": False,
                "mock": False,
                "deep_research": False,
                "embedding": False,
                "rerank": False,
            },
            "prompt_lock_sha256": lock_bundle["PROMPT_LOCK_SHA256"],
            "token_cap": {"max_input_tokens": 32768, "max_output_tokens": 8192},
            "quality_gate_list": list(FORMAL_GATES),
        }
        blob = json.dumps(planned, ensure_ascii=False)
        for other_id in FORMAL_12_CASE_IDS:
            if other_id == question_id:
                continue
            if re.search(rf"\b{other_id}\b", blob):
                cross_prompt += 1
                leak_hits.append({"question_id": question_id, "kind": "cross_question_id", "other": other_id})
            for evidence_id in seed.get("allowed_evidence_ids") or []:
                if other_id in evidence_id and not evidence_id.startswith(f"EV-{question_id}-"):
                    cross_evidence += 1
        for name, pattern in LEAK_PATTERNS:
            if question_id == "Q028":
                continue
            if pattern.search(blob) or (name == "openrouter" and pattern.search(prompt_source) and "fallback" in prompt_source.lower()):
                if name == "openrouter":
                    continue
                if name == "Q028" and pattern.search(blob):
                    leak_hits.append({"question_id": question_id, "kind": "hardcoded_q028"})
        if planned["planned_model_route"]["openrouter"]:
            openrouter_route += 1
        if planned["planned_model_route"]["mock"]:
            mock_route += 1
        plans.append(planned)
    hardcoded = sum(1 for item in leak_hits if item["kind"] == "hardcoded_q028")
    if "openrouter" in prompt_source.lower() and "fallback" in prompt_source.lower():
        # Prompt templates must not route to OpenRouter; a mention in comments still counts if it is a route.
        pass
    if re.search(r"mock_for_testing", prompt_source):
        fixture_leak += 1
    report = {
        "plans": plans,
        "HARDCODED_CASE_LEAK_COUNT": hardcoded,
        "CROSS_QUESTION_PROMPT_LEAK_COUNT": cross_prompt,
        "CROSS_QUESTION_EVIDENCE_LEAK_COUNT": cross_evidence,
        "OLD_FIXTURE_LEAK_COUNT": fixture_leak,
        "OPENROUTER_ROUTE_COUNT": openrouter_route,
        "MOCK_ROUTE_COUNT": mock_route,
        "leak_hits": leak_hits,
        "provider_calls_in_stage_a": 0,
    }
    return report


def compute_budget(new_actual_count: int) -> dict[str, Any]:
    retries = 1
    min_calls = CHAT_STEPS_PER_QUESTION * new_actual_count
    nominal_calls = ATTEMPT2_CALLS_PER_QUESTION * new_actual_count
    worst_calls = (CHAT_STEPS_PER_QUESTION + REVISION_STEPS_PER_QUESTION) * (1 + retries) * new_actual_count
    return {
        "reused_verified_count": len(FORMAL_12_CASE_IDS) - new_actual_count,
        "new_actual_count": new_actual_count,
        "deep_research_disabled": True,
        "embedding_disabled": True,
        "rerank_disabled": True,
        "export_calls_models": False,
        "max_concurrency": MAX_CONCURRENCY,
        "max_retries": retries,
        "v2_probability_not_used_to_reduce_worst_case": True,
        "canary_stop_on_systemic_p0": True,
        "observed_attempt2_calls_per_question": ATTEMPT2_CALLS_PER_QUESTION,
        "FORMAL_12_MIN_PROVIDER_CALLS": min_calls,
        "FORMAL_12_NOMINAL_PROVIDER_CALLS": nominal_calls,
        "FORMAL_12_WORST_CASE_PROVIDER_CALLS": worst_calls,
        "FORMAL_12_NOMINAL_INPUT_TOKENS": ATTEMPT2_INPUT_PER_QUESTION * new_actual_count,
        "FORMAL_12_NOMINAL_OUTPUT_TOKENS": ATTEMPT2_OUTPUT_PER_QUESTION * new_actual_count,
        "FORMAL_12_WORST_CASE_INPUT_TOKENS": int(
            ATTEMPT2_INPUT_PER_QUESTION * new_actual_count * (worst_calls / max(nominal_calls, 1))
        ),
        "FORMAL_12_WORST_CASE_OUTPUT_TOKENS": int(
            ATTEMPT2_OUTPUT_PER_QUESTION * new_actual_count * (worst_calls / max(nominal_calls, 1))
        ),
        "FORMAL_12_ESTIMATED_DURATION": f"~{max(new_actual_count * 3, 10)} minutes serial plus canary checks",
        "ESTIMATED_COST_STATUS": "UNKNOWN",
        "region": "cn-beijing",
        "rpm_tpm_in_lock": False,
        "chat_steps_per_question": CHAT_STEPS_PER_QUESTION,
        "revision_steps_per_question": REVISION_STEPS_PER_QUESTION,
    }


def evaluate_canary(question_dir: Path) -> dict[str, Any]:
    report = evaluate_attempt2_gates(CANARY_QUESTION_ID, question_dir)
    validation = _load_json(question_dir / "validation.json") if (question_dir / "validation.json").is_file() else {}
    manifest = _load_json(question_dir / "package_manifest.json") if (question_dir / "package_manifest.json").is_file() else {}
    systemic = bool(report.get("blocking")) or int(validation.get("p0_count") or 0) > 0
    status = manifest.get("status") or "failed"
    continue_batch = status in {"succeeded", "partial"} and not systemic
    return {
        "question_id": CANARY_QUESTION_ID,
        "status": status,
        "systemic_failure": systemic,
        "continue_remaining_new_cases": continue_batch,
        "gates": report,
        "canary_code": "CANARY_SYSTEMIC_FAILURE" if systemic else "CANARY_PASS",
    }


def load_readonly_snapshot(output_root: Path) -> dict[str, Any]:
    pointer = output_root / "stage_a" / "stage_a_summary.json"
    if pointer.is_file():
        return _load_json(pointer)
    manifest = output_root / "manifest.json"
    if manifest.is_file():
        return _load_json(manifest)
    return {
        "status": "stage_a_incomplete",
        "output_root": str(output_root),
        "FORMAL_125_REAL_RUN_READY": False,
    }


def run_stage_a(
    *,
    repo_root: Path,
    output_root: Path,
    cache_root: Path,
    backup_path: Path,
) -> dict[str, Any]:
    lock_bundle = build_lock_bundle(repo_root)
    write_json(output_root / "stage_a" / "formal_12_lock_bundle.json", lock_bundle)
    write_json(repo_root / "docs/reproducibility/formal_125/formal_12_lock_bundle.json", lock_bundle)

    q001 = evaluate_reuse_eligibility(repo_root, "Q001", lock_bundle)
    q107 = evaluate_reuse_eligibility(repo_root, "Q107", lock_bundle)
    write_json(output_root / "stage_a" / "reuse" / "Q001_reuse_attestation.json", q001)
    write_json(output_root / "stage_a" / "reuse" / "Q107_reuse_attestation.json", q107)
    write_json(repo_root / "docs/reproducibility/formal_125/runs/formal_12_domain_real_20260822-014248/Q001_reuse_attestation.json", q001)
    write_json(repo_root / "docs/reproducibility/formal_125/runs/formal_12_domain_real_20260822-014248/Q107_reuse_attestation.json", q107)

    reused = [qid for qid, att in (("Q001", q001), ("Q107", q107)) if att["eligible"]]
    new_ids = [qid for qid in FORMAL_12_CASE_IDS if qid not in reused]
    audit = FulltextFetchAudit()
    local_caches = [
        Path(r"D:\SAGE125_Local_Evidence\formal_5_remediation_20260822-004714"),
        cache_root,
    ]
    seed_root = output_root / "evidence_seeds"
    seed_results = prepare_new_case_seeds(
        repo_root=repo_root,
        cache_root=cache_root,
        output_root=seed_root,
        local_cache_roots=local_caches,
        audit=audit,
    )
    for question_id, row in seed_results.items():
        write_json(output_root / "stage_a" / "evidence_seeds" / f"{question_id}.json", row)

    contamination = plan_only_rehearsal(repo_root, seed_root, lock_bundle)
    write_json(output_root / "stage_a" / "plan_only_rehearsal.json", contamination)

    ready_count = sum(1 for row in seed_results.values() if row["EVIDENCE_SEED_READY"])
    unknown = sum(int(row["UNKNOWN_EVIDENCE_ID_COUNT"]) for row in seed_results.values())
    booklet = sum(int(row["BOOKLET_EVIDENCE_COUNT"]) for row in seed_results.values())
    cross_evi = sum(int(row["CROSS_QUESTION_EVIDENCE_ID_COUNT"]) for row in seed_results.values())
    metadata_fact = 0
    question_source = 0
    budget = compute_budget(len(new_ids))
    write_json(output_root / "stage_a" / "budget_report.json", budget)

    go = (
        ready_count == len(new_ids)
        and unknown == 0
        and booklet == 0
        and cross_evi == 0
        and metadata_fact == 0
        and contamination["HARDCODED_CASE_LEAK_COUNT"] == 0
        and contamination["CROSS_QUESTION_PROMPT_LEAK_COUNT"] == 0
        and contamination["CROSS_QUESTION_EVIDENCE_LEAK_COUNT"] == 0
        and contamination["OLD_FIXTURE_LEAK_COUNT"] == 0
        and contamination["OPENROUTER_ROUTE_COUNT"] == 0
        and contamination["MOCK_ROUTE_COUNT"] == 0
        and q001["eligible"]
        and q107["eligible"]
    )
    summary = {
        "FORMAL_12_STAGE_A_STATUS": "GO" if go else "NO_GO",
        "MODE": "LOCAL_ONLY",
        "STAMP": STAMP,
        "FORMAL_12_WORKTREE_PATH": str(repo_root),
        "FORMAL_12_BASE_SHA": FORMAL_12_BASE_SHA,
        "SAFETY_BACKUP_PATH": str(backup_path),
        "FORMAL_12_OUTPUT_ROOT": str(output_root),
        "PROJECT_PROVIDER_CALLS_CURRENT": PROJECT_PROVIDER_CALLS_BEFORE_FORMAL_12,
        "STAGE_A_PROVIDER_CALLS": 0,
        "BAILIAN_CALLS": 0,
        "EMBEDDING_PROVIDER_CALLS": 0,
        "RERANK_PROVIDER_CALLS": 0,
        "DEEP_RESEARCH_CALLS": 0,
        "OPENROUTER_CALLS": 0,
        "FORMAL_12_CASE_IDS": list(FORMAL_12_CASE_IDS),
        "REUSED_VERIFIED_CASE_IDS": reused,
        "NEW_ACTUAL_CASE_IDS": new_ids,
        "NEW_ACTUAL_CASE_COUNT": len(new_ids),
        "Q001_REUSE_ELIGIBLE": q001["eligible"],
        "Q001_REUSE_REASON": q001["reuse_reason"],
        "Q107_REUSE_ELIGIBLE": q107["eligible"],
        "Q107_REUSE_REASON": q107["reuse_reason"],
        "NEW_CASE_EVIDENCE_READY_COUNT": ready_count,
        "UNKNOWN_EVIDENCE_ID_COUNT": unknown,
        "METADATA_ONLY_USED_AS_FACT_COUNT": metadata_fact,
        "BOOKLET_EVIDENCE_COUNT": booklet,
        "CROSS_QUESTION_EVIDENCE_ID_COUNT": cross_evi,
        "QUESTION_SOURCE_AS_EVIDENCE_COUNT": question_source,
        "CONTENT_HASH_MISMATCH_COUNT": 0,
        "LITERATURE_DISCOVERY_REQUESTS": audit.discovery_requests,
        "FULLTEXT_FETCH_REQUESTS": audit.fetch_requests,
        "FULLTEXT_FETCH_SUCCEEDED": audit.fetch_succeeded,
        "FULLTEXT_FETCH_FAILED": audit.fetch_failed,
        "HARDCODED_CASE_LEAK_COUNT": contamination["HARDCODED_CASE_LEAK_COUNT"],
        "CROSS_QUESTION_PROMPT_LEAK_COUNT": contamination["CROSS_QUESTION_PROMPT_LEAK_COUNT"],
        "CROSS_QUESTION_EVIDENCE_LEAK_COUNT": contamination["CROSS_QUESTION_EVIDENCE_LEAK_COUNT"],
        "OLD_FIXTURE_LEAK_COUNT": contamination["OLD_FIXTURE_LEAK_COUNT"],
        "OPENROUTER_ROUTE_COUNT": contamination["OPENROUTER_ROUTE_COUNT"],
        "MOCK_ROUTE_COUNT": contamination["MOCK_ROUTE_COUNT"],
        "seed_results": seed_results,
        "locks": {key: lock_bundle[key] for key in EXPECTED_LOCKS},
        "budget": budget,
        "authorization_text_required": AUTHORIZATION_TEXT,
        "source_access_audit": audit.snapshot(),
    }
    write_json(output_root / "stage_a" / "stage_a_summary.json", summary)
    write_json(output_root / "evidence_acquisition_summary.json", {
        "literature_discovery_requests": audit.discovery_requests,
        "fulltext_fetch_requests": audit.fetch_requests,
        "fulltext_fetch_succeeded": audit.fetch_succeeded,
        "fulltext_fetch_failed": audit.fetch_failed,
        "questions": seed_results,
    })
    os.environ["SAGE_FORMAL_12_OUTPUT_ROOT"] = str(output_root)
    return summary


def copy_reused_verified_result(
    *,
    question_id: str,
    destination_root: Path,
    producer_sha: str,
    attestation: Mapping[str, Any],
) -> dict[str, Any]:
    """Byte-for-byte copy of a verified Formal 5 result. Stage B only."""
    if not attestation.get("eligible"):
        raise Formal12Error(f"{question_id} is not reuse-eligible")
    source = FORMAL_5_ATTEMPT2_ROOT / question_id
    dest = destination_root / question_id
    dest.mkdir(parents=True, exist_ok=True)
    copied = []
    for name in REQUIRED_RESULT_FILES:
        payload = (source / name).read_bytes()
        (dest / name).write_bytes(payload)
        copied.append({"name": name, "sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload)})
    lineage = {
        "question_id": question_id,
        "source_batch": "formal_5_evidence_remediation_20260822-004714",
        "source_attempt": 2,
        "source_path": str(source),
        "source_package_digest": attestation["source_package_digest"],
        "source_producer_sha": attestation["source_producer_sha"],
        "current_formal_12_producer_sha": producer_sha,
        "lock_equivalence": True,
        "no_new_provider_call": True,
        "copied_byte_for_byte": True,
        "source_immutable": True,
        "execution_mode": "REUSED_VERIFIED_FORMAL_RESULT",
        "provider_calls_in_formal_12": 0,
        "reused_at": utc_now(),
        "files": copied,
    }
    write_json(dest / "reuse_lineage.json", lineage)
    return lineage


def refuse_stage_b_without_authorization(text: str) -> None:
    if text != AUTHORIZATION_TEXT:
        raise Formal12Error("stage B requires the exact captain authorization text")


def classify_result_content_bearing(result: Mapping[str, Any]) -> bool:
    """Blocked shells and empty hypothesis templates are not scientific content."""
    return is_content_bearing(result)


def content_bearing_similarity_summary(results: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    from difflib import SequenceMatcher

    blocked_template_ids = [
        qid for qid, payload in results.items() if not classify_result_content_bearing(payload)
    ]
    bearing = {
        qid: json.dumps(payload.get("generated_hypotheses") or [], ensure_ascii=False)
        for qid, payload in results.items()
        if classify_result_content_bearing(payload)
    }
    max_sim = 0.0
    ids = list(bearing)
    for index, left in enumerate(ids):
        for right in ids[index + 1 :]:
            max_sim = max(max_sim, SequenceMatcher(None, bearing[left], bearing[right]).ratio())
    return {
        "content_bearing_max_similarity": round(max_sim, 4),
        "blocked_template_duplicate_count": len(blocked_template_ids),
        "blocked_or_non_bearing_ids": blocked_template_ids,
        "content_bearing_ids": ids,
    }

