"""
app.ui.validators —— 前端侧轻量校验。

在真实模式运行前检查前置条件（Key/索引/API/问题清单），返回是否可运行与
需修复项，避免白屏。不涉及任何 Key 明文。
"""

from __future__ import annotations


def check_real_mode_ready(health: dict, use_local_rag: bool, api_connected: bool) -> tuple[bool, list[str]]:
    """
    校验真实模式运行前置条件。

    参数：
        health:        /health 或 in-process 健康信息 dict。
        use_local_rag: 是否启用本地 RAG（启用则要求索引就绪）。
        api_connected: API 是否可达。

    返回：
        (是否就绪, 需修复项文案列表)。
    """
    issues: list[str] = []
    # 百炼配置。
    if not health.get("qwen_config_loaded"):
        issues.append("未配置 DASHSCOPE_API_KEY：请运行 py -3 scripts/setup_env.py。")
    # 问题清单。
    if not health.get("questions_count"):
        issues.append("缺少 questions_125.json：请运行 py -3 scripts/extract_125_questions.py。")
    # 用户文献库为空不是阻塞项：Local RAG 会跳过，并由开放文献/needs_data 接手。
    # 只有治理服务本身不可用才阻止，绝不回退到题源 sjtu-booklet.pdf。
    if use_local_rag and health.get("rag_index_status") == "unavailable":
        issues.append("用户本地文献库不可用：请检查 data/raw/uploads 的读写权限。")
    # API 未启动（真实模式不静默 in-process fallback）。
    if not api_connected:
        issues.append("API 未启动：请运行 uvicorn app.api.main:app --reload --port 8000。")
    return (len(issues) == 0, issues)


def check_mock_mode_ready(health: dict) -> tuple[bool, list[str]]:
    """
    校验 mock 模式运行前置条件（仅需问题清单）。

    参数：
        health: 健康信息 dict。

    返回：
        (是否就绪, 需修复项文案列表)。
    """
    issues: list[str] = []
    if not health.get("questions_count"):
        issues.append("缺少 questions_125.json：请运行 py -3 scripts/extract_125_questions.py。")
    return (len(issues) == 0, issues)
