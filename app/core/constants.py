"""
app.core.constants —— 全局常量与安全清单。

集中定义：
    - 允许的生成模型前缀（仅 Qwen/千问）；
    - 明确禁用的非千问生成模型厂商关键字（用于运行期与测试期校验）；
    - 项目内通用的枚举与阶段名称常量。

安全意义：
    通过 FORBIDDEN_MODEL_KEYWORDS 与 is_allowed_generation_model()，
    可在客户端与测试中强制“仅千问生成模型”的硬性约束。
"""

from __future__ import annotations

from typing import Iterable

# 允许作为“生成模型”的模型名前缀集合：一律为 Qwen/千问系列。
ALLOWED_GENERATION_MODEL_PREFIXES: tuple[str, ...] = (
    "qwen",  # 覆盖 qwen3.x-flash / plus / max、qwen-deep-research 等
)

# 明确禁用的非千问生成模型厂商 / 家族关键字（小写匹配）。
# 说明：这些仅针对“生成模型”，不影响作为 HTTP 客户端的 openai SDK 本身。
FORBIDDEN_MODEL_KEYWORDS: tuple[str, ...] = (
    "gpt",        # OpenAI GPT 系列
    "o1", "o3",   # OpenAI o 系列
    "claude",     # Anthropic
    "gemini",     # Google
    "deepseek",   # DeepSeek
    "kimi",       # Moonshot
    "glm",        # 智谱 GLM
    "minimax",    # MiniMax
)

# 工作流阶段名称常量：与 agents 一一对应，便于状态机与日志引用。
STAGE_QUESTION_PARSER = "question_parser"
STAGE_QUERY_PLANNER = "query_planner"
STAGE_LOCAL_RAG = "local_rag"
STAGE_DEEP_RESEARCH = "deep_research"
STAGE_EVIDENCE_EXTRACTOR = "evidence_extractor"
STAGE_HYPOTHESIS_GENERATOR = "hypothesis_generator"
STAGE_EXPERIMENT_DESIGNER = "experiment_designer"
STAGE_SCIENTIFIC_REVIEWER = "scientific_reviewer"
STAGE_REPORT_WRITER = "report_writer"
STAGE_SCHEMA_VALIDATOR = "schema_validator"

# 有序的流水线阶段列表，供 pipeline 编排与可视化使用。
PIPELINE_STAGES: tuple[str, ...] = (
    STAGE_QUESTION_PARSER,
    STAGE_QUERY_PLANNER,
    STAGE_LOCAL_RAG,
    STAGE_DEEP_RESEARCH,
    STAGE_EVIDENCE_EXTRACTOR,
    STAGE_HYPOTHESIS_GENERATOR,
    STAGE_EXPERIMENT_DESIGNER,
    STAGE_SCIENTIFIC_REVIEWER,
    STAGE_REPORT_WRITER,
    STAGE_SCHEMA_VALIDATOR,
)


def is_allowed_generation_model(model_name: str) -> bool:
    """
    判断给定生成模型名称是否满足“仅千问”硬性约束。

    参数：
        model_name: 待校验的模型名称，例如 "qwen3.7-max"。

    返回：
        True  —— 模型名以允许前缀开头且不含任何禁用关键字；
        False —— 否则（应拒绝调用）。
    """
    # 空名称视为非法。
    if not model_name:
        return False
    # 统一小写后进行匹配，避免大小写绕过。
    name = model_name.lower()
    # 命中任一禁用关键字即拒绝。
    if any(keyword in name for keyword in FORBIDDEN_MODEL_KEYWORDS):
        return False
    # 必须以允许的千问前缀开头。
    return name.startswith(ALLOWED_GENERATION_MODEL_PREFIXES)


def assert_allowed_generation_models(model_names: Iterable[str]) -> None:
    """
    批量断言一组生成模型名称均为千问模型，否则抛出 ValueError。

    参数：
        model_names: 待校验的模型名称集合。

    异常：
        ValueError: 当存在任一非千问生成模型时抛出，提示违规模型名。
    """
    # 收集所有不合规的模型名，一次性报告，便于排查。
    invalid = [m for m in model_names if not is_allowed_generation_model(m)]
    if invalid:
        raise ValueError(
            f"检测到非千问生成模型，违反安全约束：{invalid}。仅允许 Qwen/千问模型。"
        )
