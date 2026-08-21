"""Build formal 125 preflight locks, evidence package, and plan-only 5-case rehearsal."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from app.agents import prompts as prompt_module
from app.batch.five_run_preflight import FROZEN_QUESTION_IDS
from app.core.config import Settings, get_settings
from app.formal125 import REQUIRED_RESULT_FILES, SIMILARITY_REVIEW_THRESHOLD
from app.formal125.authorization import authorization_schema
from app.formal125.catalog import (
    AUTHORITATIVE_SOURCE_SHA256,
    build_catalog_lock,
    build_domain_map,
    build_formal_12_manifest,
    build_formal_5_manifest,
    build_manual_review_24_manifest,
    write_production_source,
)
from app.formal125.dry_run import run_formal_125_dry_run
from app.formal125.hashes import sha256_canonical_json, sha256_file, sha256_text_lf, write_json
from app.formal125.pipeline_plan import plan_question_calls, scale_budget
from app.quality.gates import (
    AgentTraceGate,
    ArtifactPresenceGate,
    ExecutionTruthGate,
    HumanFeedbackPropagationGate,
    build_default_quality_gates,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
LOCK_ROOT = REPO_ROOT / "docs" / "reproducibility" / "formal_125"
CATALOG_DIR = LOCK_ROOT / "catalog"
SOURCE_CANDIDATES = (
    CATALOG_DIR / "questions_125.source.json",
    Path(r"D:\SAGE125-AI-Scientist\data\processed\questions_125.json"),
)

LEAK_PATTERNS = (
    re.compile(r"\bQ028\b"),
    re.compile(r"\bWDBC\b", re.IGNORECASE),
    re.compile(r"口蹄疫|非洲猪瘟|animal epidemic", re.IGNORECASE),
    re.compile(r"DASHSCOPE_API_KEY\s*="),
    re.compile(r"sk-[A-Za-z0-9]{8,}"),
)

PROMPT_NAMES = (
    "COMMON_SCIENTIST_RULES",
    "QUESTION_PARSER_PROMPT",
    "QUERY_PLANNER_PROMPT",
    "EVIDENCE_EXTRACTOR_PROMPT",
    "HYPOTHESIS_GENERATOR_PROMPT",
    "EXPERIMENT_DESIGNER_PROMPT",
    "SCIENTIFIC_REVIEWER_PROMPT",
    "REPORT_WRITER_PROMPT",
    "SCHEMA_VALIDATOR_PROMPT",
    "SUPERVISOR_PROMPT",
)

FORMAL_GATES = (
    "question_title_consistency",
    "required_fields",
    "evidence_id_existence",
    "source_type",
    "quote_locator",
    "unsupported_claim",
    "booklet_contamination",
    "hallucinated_reference",
    "actual_planned_expected",
    "provider_request_audit",
    "mock_detection",
    "cross_question_leakage",
    "duplicate_hypothesis",
    "output_file_completeness",
    "checksum",
    "scientific_overclaim",
    "p0_fail_closed",
    "p1_fail_closed",
    "secret_scan",
    "path_traversal",
    "pdf_integrity",
)


class PreflightError(RuntimeError):
    """Preflight generation failed."""


def _present(value: str | None) -> bool:
    return bool(value and value.strip())


def locate_source_catalog() -> Path:
    for candidate in SOURCE_CANDIDATES:
        if candidate.is_file() and sha256_file(candidate) == AUTHORITATIVE_SOURCE_SHA256:
            return candidate
    raise PreflightError("authoritative questions_125.json was not found")


def install_source_catalog(destination: Path | None = None) -> Path:
    target = destination or (CATALOG_DIR / "questions_125.source.json")
    source = locate_source_catalog()
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != target.resolve():
        target.write_bytes(source.read_bytes())
    if sha256_file(target) != AUTHORITATIVE_SOURCE_SHA256:
        raise PreflightError("copied catalog SHA-256 mismatch")
    return target


def scan_prompt_leaks(text: str) -> list[str]:
    hits = []
    for pattern in LEAK_PATTERNS:
        if pattern.search(text):
            hits.append(pattern.pattern)
    return hits


def build_prompt_lock() -> dict[str, Any]:
    prompts_path = Path(prompt_module.__file__)
    source = prompts_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    assigned = {
        node.targets[0].id
        for node in tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
    }
    prompts = []
    leak_count = 0
    for name in PROMPT_NAMES:
        if name not in assigned:
            raise PreflightError(f"prompt {name} is not defined in prompts.py")
        template = getattr(prompt_module, name)
        leaks = scan_prompt_leaks(template)
        leak_count += len(leaks)
        role = name.replace("_PROMPT", "").replace("_RULES", "").lower()
        prompts.append(
            {
                "prompt_id": name,
                "role": role,
                "source_path": "app/agents/prompts.py",
                "template": template,
                "required_context": [
                    "question_id",
                    "question_hash",
                    "context_id",
                ],
                "output_schema": "app/core/agent_schemas.py",
                "model_role": {
                    "QUESTION_PARSER_PROMPT": "fast",
                    "QUERY_PLANNER_PROMPT": "balanced",
                    "EVIDENCE_EXTRACTOR_PROMPT": "balanced",
                    "HYPOTHESIS_GENERATOR_PROMPT": "strong",
                    "EXPERIMENT_DESIGNER_PROMPT": "strong",
                    "SCIENTIFIC_REVIEWER_PROMPT": "strong",
                    "REPORT_WRITER_PROMPT": "balanced",
                    "SCHEMA_VALIDATOR_PROMPT": "fast",
                    "SUPERVISOR_PROMPT": "none_llm_strategy",
                    "COMMON_SCIENTIST_RULES": "shared",
                }[name],
                "temperature": 0.1,
                "max_tokens": int(get_settings().llm_max_output_tokens),
                "normalized_prompt_sha256": sha256_text_lf(template),
                "version": "sage125-agent-prompts-formal125-v1",
                "mock_actual_guard": "actual_run_forbids_mock_and_openrouter",
                "leak_hits": leaks,
            }
        )
    payload = {
        "lock_version": "formal125.prompt.v1",
        "source_path": "app/agents/prompts.py",
        "prompt_count": len(prompts),
        "prompts": prompts,
        "hardcoded_case_leak_count": leak_count,
        "cross_question_prompt_leak_count": leak_count,
        "flagship_prompts_excluded": [
            "app/execution/flagship_reviewer.py",
            "app/execution/flagship_revision.py",
        ],
        "flagship_exclusion_reason": (
            "Q028 flagship reviewer/revision prompts are regression-only and "
            "must not enter the formal 125 generation path."
        ),
        "input_binding_required": [
            "question_id",
            "question_hash",
            "context_id",
        ],
    }
    payload["prompt_lock_sha256"] = sha256_canonical_json(
        {key: value for key, value in payload.items() if key != "prompt_lock_sha256"}
    )
    if leak_count:
        raise PreflightError("formal 125 prompts contain hardcoded case leaks")
    return payload


def build_model_lock(settings: Settings | None = None) -> dict[str, Any]:
    resolved = settings or get_settings()
    payload = {
        "lock_version": "formal125.model.v1",
        "provider": resolved.llm_provider,
        "openrouter_fallback_allowed": False,
        "mock_fallback_allowed": False,
        "silent_model_switch_allowed": False,
        "model_roles": {
            "chat_fast": resolved.qwen_fast_model,
            "chat_balanced": resolved.qwen_balanced_model,
            "chat_strong": resolved.qwen_strong_model,
            "reviewer": resolved.qwen_strong_model,
            "deep_research": resolved.qwen_deep_research_model,
            "embedding": resolved.bailian_embedding_model,
            "rerank": resolved.bailian_rerank_model,
        },
        "exact_model_ids": [
            resolved.qwen_fast_model,
            resolved.qwen_balanced_model,
            resolved.qwen_strong_model,
            resolved.qwen_deep_research_model,
            resolved.bailian_embedding_model,
            resolved.bailian_rerank_model,
        ],
        "model_config": {
            "temperature": 0.1,
            "timeout_seconds": resolved.llm_timeout_seconds,
            "connect_timeout_seconds": resolved.llm_connect_timeout_seconds,
            "max_retries": resolved.llm_max_retries,
            "max_output_tokens": resolved.llm_max_output_tokens,
            "max_input_tokens": 32768,
            "thinking": "disabled_unless_model_default",
            "search": "deep_research_only",
        },
        "retry": {"max_retries": resolved.llm_max_retries, "retryable_http": [429, 500, 502, 503]},
        "timeout": {"read_seconds": resolved.llm_timeout_seconds, "connect_seconds": resolved.llm_connect_timeout_seconds},
        "token_caps": {"max_input_tokens": 32768, "max_output_tokens": resolved.llm_max_output_tokens},
        "region": resolved.dashscope_region,
        "base_url_pattern": "https://dashscope.{region}.aliyuncs.com/compatible-mode/v1",
        "variable_names": {
            "api_key": "DASHSCOPE_API_KEY",
            "workspace_id": "WORKSPACE_ID",
            "provider": "LLM_PROVIDER",
            "region": "DASHSCOPE_REGION",
            "base_url": "DASHSCOPE_BASE_URL",
        },
        "api_key_present": _present(resolved.dashscope_api_key),
        "workspace_present": _present(resolved.workspace_id),
        "bailian_configured": (
            resolved.llm_provider == "bailian"
            and _present(resolved.dashscope_api_key)
            and _present(resolved.workspace_id)
        ),
    }
    if payload["provider"] != "bailian":
        raise PreflightError("formal 125 provider must be bailian")
    payload["model_lock_sha256"] = sha256_canonical_json(
        {key: value for key, value in payload.items() if key != "model_lock_sha256"}
    )
    return payload


def build_output_contract() -> dict[str, Any]:
    payload = {
        "lock_version": "formal125.output-contract.v1",
        "required_files": list(REQUIRED_RESULT_FILES),
        "required_file_count_per_question": len(REQUIRED_RESULT_FILES),
        "required_fields": [
            "Problem",
            "Rationale",
            "Technical Details",
            "Datasets Source",
            "Target",
            "Title",
            "Abstract",
            "Methods",
            "Experiments",
            "Results",
            "References",
        ],
        "rules": {
            "md_json_pdf_semantically_consistent": True,
            "evidence_ids_must_exist": True,
            "references_must_backlink": True,
            "booklet_not_scholarly_evidence": True,
            "no_fictional_metrics_without_actual_execution": True,
            "actual_planned_expected_strict": True,
            "no_success_without_request_id": True,
            "incomplete_files_cannot_be_completed": True,
            "pdf_must_not_be_blank_or_raw_markdown": True,
            "every_file_in_checksums": True,
            "package_manifest_matches_files": True,
            "agent_trace_redacts_secrets": True,
            "evidence_cards_need_quote_or_locator": True,
            "validation_includes_p0_p1": True,
            "provider_audit_records_failures_and_retries": True,
        },
        "t07_legacy_aliases": {
            "report.md": "result.md",
            "report.pdf": "result.pdf",
        },
    }
    payload["output_contract_sha256"] = sha256_canonical_json(
        {key: value for key, value in payload.items() if key != "output_contract_sha256"}
    )
    return payload


def build_evidence_policy() -> dict[str, Any]:
    payload = {
        "lock_version": "formal125.evidence.v1",
        "formal_evidence_mode": "local_rag_plus_open_literature_plus_optional_deep_research",
        "question_source": "125 Questions booklet; evidence_eligible=false",
        "scholarly_evidence": [
            "user_upload_fulltext_index",
            "openalex",
            "crossref",
            "arxiv",
            "deep_research_cards_requiring_downstream_verification",
        ],
        "metadata_only": ["DOI/title hits without quote or locator"],
        "dataset_sources_allowed": ["named public datasets with locator", "user-provided data with provenance"],
        "cannot_support_scientific_facts": ["booklet", "mock", "synthetic", "unquoted metadata"],
        "minimum_evidence_per_question": 1,
        "insufficient_evidence_policy": "retain knowledge_gaps; cannot mark completed/passed",
        "conflict_policy": "record disputed_points; do not force a conclusion",
        "locator_required": True,
        "cache_and_index": {
            "user_library_index": "app.rag.library_manager.USER_LIBRARY_ZVEC_DIR",
            "booklet_index_isolated": True,
            "rebuildable_in_clean_environment": True,
            "gitignored_index_not_authority": True,
        },
        "license_policy": "preserve source license; do not treat booklet as corpus evidence",
        "offline_or_retrieval_failure": "continue with warnings; evidence_insufficient=true; no invented papers",
        "live_retrieval_this_stage": False,
        "booklet_contamination_count": 0,
        "booklet_contamination_rule": "booklet cards cannot enter scholarly evidence corpus",
    }
    payload["evidence_policy_sha256"] = sha256_canonical_json(
        {key: value for key, value in payload.items() if key != "evidence_policy_sha256"}
    )
    return payload


def build_gate_policy() -> dict[str, Any]:
    implemented = [getattr(gate, "gate_id") for gate in build_default_quality_gates()]
    payload = {
        "lock_version": "formal125.gate.v1",
        "gate_count": len(FORMAL_GATES),
        "gates": list(FORMAL_GATES),
        "implemented_t03_gates": implemented,
        "p0_fail_closed": True,
        "p1_fail_closed": True,
        "skipped_rule_cannot_pass": True,
        "validator_exception_cannot_pass": True,
        "partial_or_blocked_cannot_look_complete": True,
        "single_question_failure_isolates": True,
        "similarity_threshold": SIMILARITY_REVIEW_THRESHOLD,
        "similarity_disposition": "human_review_only_no_auto_delete",
        "callable_gate_hooks": implemented,
    }
    payload["gate_policy_sha256"] = sha256_canonical_json(
        {key: value for key, value in payload.items() if key != "gate_policy_sha256"}
    )
    return payload


def build_batch_policy() -> dict[str, Any]:
    payload = {
        "lock_version": "formal125.batch.v1",
        "engine": "app.batch.runner.BatchRunner + app.formal125.dry_run",
        "job_count": 125,
        "states": [
            "planned",
            "queued",
            "running",
            "succeeded",
            "partial",
            "failed",
            "blocked",
            "cancelled",
            "dry_run_complete",
        ],
        "dry_run_complete_not_formal_completed": True,
        "isolation": {
            "independent_jobs": True,
            "independent_workspace": True,
            "independent_context_id": True,
            "independent_cache_namespace": True,
            "independent_output_path": True,
            "independent_checkpoint": True,
            "question_id_bound_to_input_hash": True,
        },
        "checkpoint": {
            "checksum_or_schema_validated": True,
            "corrupt_rejected": True,
            "atomic_write": True,
            "dry_run_cannot_promote_to_actual": True,
            "synthetic_cannot_produce_actual": True,
            "prompt_model_schema_mismatch_rejects_resume": True,
        },
        "retry": {
            "failed_retryable_until_limit": True,
            "non_retryable_not_retried": True,
            "max_attempts": 3,
        },
        "resume": {
            "idempotent": True,
            "completed_dry_run_not_rerun": True,
            "process_restart_restores_from_checkpoint": True,
        },
    }
    payload["batch_policy_sha256"] = sha256_canonical_json(
        {key: value for key, value in payload.items() if key != "batch_policy_sha256"}
    )
    return payload


def build_budget_plan(model_lock: Mapping[str, Any]) -> dict[str, Any]:
    per_question = plan_question_calls()
    five = scale_budget(per_question, 5)
    twelve = scale_budget(per_question, 12)
    full = scale_budget(per_question, 125)
    payload = {
        "lock_version": "formal125.budget.v1",
        "derived_from": per_question["derived_from"],
        "per_question": per_question,
        "FORMAL_5_MAX_PROVIDER_CALLS": five["max_provider_calls"],
        "FORMAL_12_MAX_PROVIDER_CALLS": twelve["max_provider_calls"],
        "FORMAL_125_MAX_PROVIDER_CALLS": full["max_provider_calls"],
        "FORMAL_5_MAX_INPUT_TOKENS": five["max_input_tokens"],
        "FORMAL_5_MAX_OUTPUT_TOKENS": five["max_output_tokens"],
        "FORMAL_125_MAX_INPUT_TOKENS": full["max_input_tokens"],
        "FORMAL_125_MAX_OUTPUT_TOKENS": full["max_output_tokens"],
        "MAX_CONCURRENCY": per_question["max_concurrency"],
        "MAX_RETRIES_PER_STEP": per_question["max_retries_per_step"],
        "ESTIMATED_COST_STATUS": "UNKNOWN",
        "model_lock_sha256": model_lock["model_lock_sha256"],
        "duration_estimate": {
            "unit": "minutes",
            "formal_5_range": [20, 120],
            "formal_12_range": [60, 360],
            "formal_125_range": [600, 3600],
            "basis": "serial max_concurrency=1 plus retry worst case; not a price estimate",
        },
    }
    payload["budget_plan_sha256"] = sha256_canonical_json(
        {key: value for key, value in payload.items() if key != "budget_plan_sha256"}
    )
    return payload


def build_formal_5_plan(
    catalog: Mapping[str, Any],
    model_lock: Mapping[str, Any],
    prompt_lock: Mapping[str, Any],
    budget: Mapping[str, Any],
    batch_id: str,
) -> dict[str, Any]:
    by_id = {item["question_id"]: item for item in catalog["questions"]}
    per_question = budget["per_question"]
    cases = []
    workspaces = []
    for qid in FROZEN_QUESTION_IDS:
        item = by_id[qid]
        workspace = f"{batch_id}/{qid}/workspace"
        workspaces.append(workspace)
        cases.append(
            {
                "question_id": qid,
                "domain": item["booklet_domain"],
                "input_hash": item["question_hash"],
                "planned_calls": per_question["max_provider_calls"],
                "model_route": {
                    "provider": "bailian",
                    "fast": model_lock["model_roles"]["chat_fast"],
                    "balanced": model_lock["model_roles"]["chat_balanced"],
                    "strong": model_lock["model_roles"]["chat_strong"],
                    "reviewer": model_lock["model_roles"]["reviewer"],
                },
                "prompt_hashes": {
                    prompt["prompt_id"]: prompt["normalized_prompt_sha256"]
                    for prompt in prompt_lock["prompts"]
                    if prompt["prompt_id"] != "COMMON_SCIENTIST_RULES"
                },
                "token_caps": model_lock["token_caps"],
                "workspace": workspace,
                "output_path": f"{batch_id}/{qid}/",
                "evidence_mode": "local_rag_plus_open_literature_plus_optional_deep_research",
                "gate_list": list(FORMAL_GATES),
                "retry_plan": {"max_retries_per_step": per_question["max_retries_per_step"]},
                "expected_required_files": list(REQUIRED_RESULT_FILES),
                "stop_conditions": [
                    "missing captain authorization",
                    "P0 or P1 open",
                    "provider audit without request_id",
                    "booklet used as scholarly evidence",
                    "Q028 canonical package is read-only regression evidence",
                ],
                "reads_old_q028_canonical_as_new_output": False,
                "mock_planned": False,
                "openrouter_planned": False,
            }
        )
    if len(set(workspaces)) != 5:
        raise PreflightError("formal 5 workspace collision")
    payload = {
        "plan_id": "formal-5-plan-only",
        "provider_calls_executed": 0,
        "total_planned_calls": 5 * per_question["max_provider_calls"],
        "cases": cases,
        "q028_canonical_is_regression_only": True,
        "status": "PASS",
    }
    payload["plan_sha256"] = sha256_canonical_json(
        {key: value for key, value in payload.items() if key != "plan_sha256"}
    )
    return payload


def _sha256_tree(root: Path) -> dict[str, str]:
    records = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            if rel in {"checksums.sha256", "package_manifest.json"}:
                continue
            records[rel] = sha256_file(path)
    return records


def write_package_checksums(root: Path) -> tuple[str, dict[str, str]]:
    records = _sha256_tree(root)
    checksum_path = root / "checksums.sha256"
    lines = [f"{digest}  {name}" for name, digest in sorted(records.items())]
    checksum_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    manifest = {
        "package": root.name,
        "file_count": len(records),
        "files": records,
        "checksums_sha256": sha256_file(checksum_path),
    }
    write_json(root / "package_manifest.json", manifest)
    return manifest["checksums_sha256"], records


def build_preflight_package(
    *,
    stamp: str,
    run_root: Path,
    commit_matrix: Mapping[str, Any],
    test_report: Mapping[str, Any],
    clean_checkout_report: Mapping[str, Any],
) -> dict[str, Any]:
    source = install_source_catalog()
    catalog = build_catalog_lock(source)
    domain_map = build_domain_map(catalog)
    formal_5 = build_formal_5_manifest(catalog)
    formal_12 = build_formal_12_manifest(catalog)
    review_24 = build_manual_review_24_manifest(catalog)
    prompt_lock = build_prompt_lock()
    model_lock = build_model_lock()
    output_contract = build_output_contract()
    evidence_policy = build_evidence_policy()
    gate_policy = build_gate_policy()
    batch_policy = build_batch_policy()
    budget = build_budget_plan(model_lock)
    auth_schema = authorization_schema()

    CATALOG_DIR.mkdir(parents=True, exist_ok=True)
    write_json(CATALOG_DIR / "questions_125.lock.json", catalog)
    write_json(CATALOG_DIR / "domain_map.lock.json", domain_map)
    write_json(LOCK_ROOT / "formal_5_selection_manifest.json", formal_5)
    write_json(LOCK_ROOT / "formal_12_domain_selection_manifest.json", formal_12)
    write_json(LOCK_ROOT / "manual_review_24_selection_manifest.json", review_24)
    write_json(LOCK_ROOT / "formal_125_model.lock.json", model_lock)
    write_json(LOCK_ROOT / "formal_125_prompt.lock.json", prompt_lock)
    write_json(LOCK_ROOT / "formal_125_output_contract.lock.json", output_contract)
    write_json(LOCK_ROOT / "formal_125_evidence_policy.lock.json", evidence_policy)
    write_json(LOCK_ROOT / "formal_125_gate_policy.lock.json", gate_policy)
    write_json(LOCK_ROOT / "formal_125_batch_policy.lock.json", batch_policy)
    write_json(LOCK_ROOT / "formal_125_budget_plan.json", budget)
    write_json(LOCK_ROOT / "run_authorization.schema.json", auth_schema)

    production_source = run_root / "questions_125.production.json"
    write_production_source(catalog, production_source)
    dry = run_formal_125_dry_run(
        source_path=production_source,
        run_root=run_root,
        batch_id=f"formal125-dry-{stamp}",
        lock_hashes={
            "catalog_hash": catalog["catalog_sha256"],
            "model_lock_hash": model_lock["model_lock_sha256"],
            "prompt_lock_hash": prompt_lock["prompt_lock_sha256"],
            "schema_lock_hash": output_contract["output_contract_sha256"],
        },
    )
    formal_5_plan = build_formal_5_plan(
        catalog,
        model_lock,
        prompt_lock,
        budget,
        batch_id=f"formal125-plan-{stamp}",
    )

    package_dir = LOCK_ROOT / "preflight" / f"FORMAL_125_PREFLIGHT_01_{stamp}"
    package_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "preflight_id": "CAPTAIN-LOCAL-FORMAL-125-PREFLIGHT-01",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stamp": stamp,
        "question_count": catalog["question_count"],
        "catalog_sha256": catalog["catalog_sha256"],
        "domain_map_sha256": domain_map["domain_map_sha256"],
        "formal_5_case_ids": formal_5["question_ids"],
        "formal_5_selection_sha256": formal_5["selection_sha256"],
        "formal_12_case_ids": formal_12["question_ids"],
        "formal_12_selection_sha256": formal_12["selection_sha256"],
        "manual_review_24_case_ids": review_24["question_ids"],
        "manual_review_24_selection_sha256": review_24["selection_sha256"],
        "model_lock_sha256": model_lock["model_lock_sha256"],
        "prompt_lock_sha256": prompt_lock["prompt_lock_sha256"],
        "output_contract_sha256": output_contract["output_contract_sha256"],
        "gate_policy_sha256": gate_policy["gate_policy_sha256"],
        "batch_policy_sha256": batch_policy["batch_policy_sha256"],
        "bailian_configured": model_lock["bailian_configured"],
        "api_key_present": model_lock["api_key_present"],
        "workspace_present": model_lock["workspace_present"],
        "prompt_count": prompt_lock["prompt_count"],
        "hardcoded_case_leak_count": prompt_lock["hardcoded_case_leak_count"],
        "booklet_contamination_count": 0,
        "dry_run": {
            "job_count": dry.job_count,
            "unique_workspace_count": dry.unique_workspace_count,
            "unique_context_count": dry.unique_context_count,
            "provider_call_count": dry.provider_call_count,
            "official_result_count": dry.official_result_count,
            "resume_status": dry.resume_status,
            "failure_isolation_status": dry.failure_isolation_status,
            "manifest_status": dry.manifest_status,
        },
        "formal_5_plan_status": formal_5_plan["status"],
        "formal_5_total_planned_calls": formal_5_plan["total_planned_calls"],
        "formal_5_provider_calls_executed": 0,
        "formal_5_real_run_ready": bool(
            model_lock["bailian_configured"] and dry.provider_call_count == 0
        ),
        "secrets_included": False,
        "official_results_included": False,
    }
    write_json(package_dir / "preflight_summary.json", summary)
    write_json(package_dir / "local_commit_integration_matrix.json", commit_matrix)
    write_json(package_dir / "questions_125.lock.json", catalog)
    write_json(package_dir / "domain_map.lock.json", domain_map)
    write_json(package_dir / "formal_5_selection_manifest.json", formal_5)
    write_json(package_dir / "formal_12_domain_selection_manifest.json", formal_12)
    write_json(package_dir / "manual_review_24_selection_manifest.json", review_24)
    write_json(package_dir / "formal_125_model.lock.json", model_lock)
    write_json(package_dir / "formal_125_prompt.lock.json", prompt_lock)
    write_json(package_dir / "formal_125_output_contract.lock.json", output_contract)
    write_json(package_dir / "formal_125_evidence_policy.lock.json", evidence_policy)
    write_json(package_dir / "formal_125_gate_policy.lock.json", gate_policy)
    write_json(package_dir / "formal_125_batch_policy.lock.json", batch_policy)
    write_json(package_dir / "formal_125_budget_plan.json", budget)
    write_json(package_dir / "run_authorization.schema.json", auth_schema)
    write_json(package_dir / "dry_run_manifest.json", dry.payload)
    write_json(
        package_dir / "dry_run_failure_injection_report.json",
        json.loads((dry.run_root / dry.batch_id / "dry_run_failure_injection_report.json").read_text(encoding="utf-8")),
    )
    write_json(package_dir / "formal_5_plan.json", formal_5_plan)
    write_json(package_dir / "test_report.json", test_report)
    write_json(package_dir / "clean_checkout_report.json", clean_checkout_report)
    (package_dir / "reproduction.md").write_text(
        "\n".join(
            [
                "# Formal 125 Preflight Reproduction",
                "",
                "This package freezes the official 125-question catalog, locks, and offline dry-run.",
                "It does not contain provider responses or official question results.",
                "",
                "```text",
                "python -m compileall app tests scripts",
                "python -m pytest tests/formal125 -q",
                "python -m pytest -q",
                "```",
                "",
            ]
        ),
        encoding="utf-8",
        newline="\n",
    )
    checksum, files = write_package_checksums(package_dir)
    return {
        "package_dir": str(package_dir),
        "summary": summary,
        "catalog": catalog,
        "domain_map": domain_map,
        "formal_5": formal_5,
        "formal_12": formal_12,
        "review_24": review_24,
        "model_lock": model_lock,
        "prompt_lock": prompt_lock,
        "output_contract": output_contract,
        "evidence_policy": evidence_policy,
        "gate_policy": gate_policy,
        "batch_policy": batch_policy,
        "budget": budget,
        "dry": dry,
        "formal_5_plan": formal_5_plan,
        "checksum": checksum,
        "files": files,
    }
