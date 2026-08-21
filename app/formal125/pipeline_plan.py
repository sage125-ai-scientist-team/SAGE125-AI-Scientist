"""Pipeline-derived provider-call budget for formal 125. No price guesses."""

from __future__ import annotations

from typing import Any

from app.core.config import Settings, get_settings


CHAT_STEPS: tuple[dict[str, str], ...] = (
    {"step_id": "question_parser", "model_role": "fast", "prompt_id": "QUESTION_PARSER_PROMPT"},
    {"step_id": "query_planner", "model_role": "balanced", "prompt_id": "QUERY_PLANNER_PROMPT"},
    {"step_id": "evidence_extractor", "model_role": "balanced", "prompt_id": "EVIDENCE_EXTRACTOR_PROMPT"},
    {"step_id": "hypothesis_generator", "model_role": "strong", "prompt_id": "HYPOTHESIS_GENERATOR_PROMPT"},
    {"step_id": "experiment_designer", "model_role": "strong", "prompt_id": "EXPERIMENT_DESIGNER_PROMPT"},
    {"step_id": "scientific_reviewer", "model_role": "strong", "prompt_id": "SCIENTIFIC_REVIEWER_PROMPT"},
    {"step_id": "report_writer", "model_role": "balanced", "prompt_id": "REPORT_WRITER_PROMPT"},
    {"step_id": "schema_validator", "model_role": "fast", "prompt_id": "SCHEMA_VALIDATOR_PROMPT"},
)
REVISION_STEPS: tuple[dict[str, str], ...] = (
    {"step_id": "revision_experiment_or_hypothesis", "model_role": "strong", "prompt_id": "EXPERIMENT_DESIGNER_PROMPT"},
    {"step_id": "revision_reviewer", "model_role": "strong", "prompt_id": "SCIENTIFIC_REVIEWER_PROMPT"},
)
DEEP_RESEARCH_STEP = {
    "step_id": "deep_research",
    "model_role": "deep_research",
    "prompt_id": "DEEP_RESEARCH_RUNTIME",
}

# QueryPlanner schema: 8-12 queries, >=3 local_rag, >=2 deep_research, >=2 open literature.
LOCAL_RAG_QUERIES_MIN = 3
LOCAL_RAG_QUERIES_MAX = 8  # 12 total minus 2 DR minus 2 open literature
MAX_CONCURRENCY = 1
MAX_INPUT_TOKENS_PER_CHAT_CALL = 32768


def _model_for_role(settings: Settings, role: str) -> str:
    mapping = {
        "fast": settings.qwen_fast_model,
        "balanced": settings.qwen_balanced_model,
        "strong": settings.qwen_strong_model,
        "deep_research": settings.qwen_deep_research_model,
        "embedding": settings.bailian_embedding_model,
        "rerank": settings.bailian_rerank_model,
    }
    return mapping[role]


def plan_question_calls(settings: Settings | None = None) -> dict[str, Any]:
    resolved = settings or get_settings()
    max_retries = int(resolved.llm_max_retries)
    attempts_per_step = 1 + max_retries
    output_cap = int(resolved.llm_max_output_tokens)

    chat_min = len(CHAT_STEPS)
    chat_max = (len(CHAT_STEPS) + len(REVISION_STEPS)) * attempts_per_step
    deep_min = 1
    deep_max = 1 * attempts_per_step
    embed_min = LOCAL_RAG_QUERIES_MIN
    embed_max = LOCAL_RAG_QUERIES_MAX * attempts_per_step
    rerank_min = LOCAL_RAG_QUERIES_MIN
    rerank_max = LOCAL_RAG_QUERIES_MAX * attempts_per_step

    min_calls = chat_min + deep_min + embed_min + rerank_min
    max_calls = chat_max + deep_max + embed_max + rerank_max
    max_input = (
        chat_max * MAX_INPUT_TOKENS_PER_CHAT_CALL
        + deep_max * MAX_INPUT_TOKENS_PER_CHAT_CALL
        + embed_max * MAX_INPUT_TOKENS_PER_CHAT_CALL
        + rerank_max * MAX_INPUT_TOKENS_PER_CHAT_CALL
    )
    max_output = (chat_max + deep_max) * output_cap
    steps = []
    for item in CHAT_STEPS:
        steps.append(
            {
                **item,
                "model_id": _model_for_role(resolved, item["model_role"]),
                "required": True,
                "min_calls": 1,
                "max_calls": attempts_per_step,
            }
        )
    steps.append(
        {
            **DEEP_RESEARCH_STEP,
            "model_id": _model_for_role(resolved, "deep_research"),
            "required": True,
            "min_calls": 1,
            "max_calls": attempts_per_step,
        }
    )
    for item in REVISION_STEPS:
        steps.append(
            {
                **item,
                "model_id": _model_for_role(resolved, item["model_role"]),
                "required": False,
                "min_calls": 0,
                "max_calls": attempts_per_step,
            }
        )
    steps.append(
        {
            "step_id": "local_rag_embedding",
            "model_role": "embedding",
            "model_id": _model_for_role(resolved, "embedding"),
            "prompt_id": None,
            "required": True,
            "min_calls": LOCAL_RAG_QUERIES_MIN,
            "max_calls": embed_max,
        }
    )
    steps.append(
        {
            "step_id": "local_rag_rerank",
            "model_role": "rerank",
            "model_id": _model_for_role(resolved, "rerank"),
            "prompt_id": None,
            "required": True,
            "min_calls": LOCAL_RAG_QUERIES_MIN,
            "max_calls": rerank_max,
        }
    )
    return {
        "derived_from": "app/workflow/pipeline.py + QueryPlanner schema constraints",
        "provider": "bailian",
        "max_retries_per_step": max_retries,
        "attempts_per_step": attempts_per_step,
        "max_concurrency": MAX_CONCURRENCY,
        "max_input_tokens_per_chat_call": MAX_INPUT_TOKENS_PER_CHAT_CALL,
        "max_output_tokens_per_chat_call": output_cap,
        "min_provider_calls": min_calls,
        "max_provider_calls": max_calls,
        "max_input_tokens": max_input,
        "max_output_tokens": max_output,
        "steps": steps,
        "openrouter_allowed": False,
        "mock_fallback_allowed": False,
        "silent_model_switch_allowed": False,
        "estimated_cost_status": "UNKNOWN",
    }


def scale_budget(per_question: dict[str, Any], question_count: int) -> dict[str, int]:
    return {
        "question_count": question_count,
        "min_provider_calls": per_question["min_provider_calls"] * question_count,
        "max_provider_calls": per_question["max_provider_calls"] * question_count,
        "max_input_tokens": per_question["max_input_tokens"] * question_count,
        "max_output_tokens": per_question["max_output_tokens"] * question_count,
    }
