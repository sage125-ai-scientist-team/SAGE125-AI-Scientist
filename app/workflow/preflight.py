"""
app.workflow.preflight —— 真实模式运行前置检查（preflight）。

在启动真实 Pipeline 前快速发现 Key / Base URL / RAG / DeepResearch 配置问题，
避免用户等待数分钟后才失败。不执行耗时网络 smoke；不泄露 API Key。
"""

from __future__ import annotations

from urllib.parse import urlparse

from app.core.config import PROJECT_ROOT, Settings, assert_qwen_model, get_settings

_WORKSPACE_PLACEHOLDER = "你的WorkspaceId"
_RAG_INDEX = PROJECT_ROOT / "data" / "index" / "user_library" / "zvec"
_CHUNKS = PROJECT_ROOT / "data" / "index" / "user_library" / "chunks.jsonl"


def run_real_preflight(
    settings: Settings | None = None,
    use_local_rag: bool = True,
    use_deep_research: bool = True,
    check_connectivity: bool = False,
) -> dict:
    """
    真实模式 preflight：检查百炼配置、模型、RAG、DeepResearch 等。

    参数：
        settings:           应用配置；缺省读取全局单例。
        use_local_rag:      是否要求 RAG 索引就绪。
        use_deep_research:  是否检查 DeepResearch 配置。

    返回：
        {
          ok, errors, warnings, fix_commands,
          can_run_real, can_run_mock
        }
    """
    s = settings or get_settings()
    errors: list[str] = []
    warnings: list[str] = []
    fix_commands: list[str] = []
    connectivity: dict = {"checked": False, "ok": None}

    # 兼容 duck-type stub（测试）与 Settings。
    qwen_ok = getattr(s, "qwen_configured", None)
    if qwen_ok is None:
        qwen_ok = bool((getattr(s, "dashscope_api_key", "") or "").strip()) and bool(
            (getattr(s, "workspace_id", "") or "").strip()
        )
    if not qwen_ok:
        errors.append("未配置 DASHSCOPE_API_KEY 或 WORKSPACE_ID")
        fix_commands.append("py -3 scripts/setup_env.py")

    # base_url 占位符或未配置
    base = (getattr(s, "dashscope_base_url", "") or "").strip()
    if not base or _WORKSPACE_PLACEHOLDER in base:
        errors.append("DASHSCOPE_BASE_URL 未替换 WorkspaceId 占位符或未配置")
        if "py -3 scripts/setup_env.py" not in fix_commands:
            fix_commands.append("py -3 scripts/setup_env.py")

    # 4) compatible-mode URL
    if base and "compatible-mode" not in base:
        warnings.append("DASHSCOPE_BASE_URL 可能不是百炼 compatible-mode URL")
    if base:
        parsed = urlparse(base)
        if parsed.scheme != "https" or not (parsed.hostname or "").endswith("aliyuncs.com"):
            errors.append("DASHSCOPE_BASE_URL 必须是 HTTPS 阿里云百炼端点")

    # 5) Qwen 模型名
    for label, model in (
        ("QWEN_FAST_MODEL", getattr(s, "qwen_fast_model", "qwen3.6-flash")),
        ("QWEN_BALANCED_MODEL", getattr(s, "qwen_balanced_model", "qwen3.7-plus")),
        ("QWEN_STRONG_MODEL", getattr(s, "qwen_strong_model", "qwen3.7-max")),
    ):
        try:
            assert_qwen_model(model)
        except ValueError as exc:
            errors.append(f"{label} 不是合法 Qwen 模型：{exc}")

    # 6) RAG index
    if use_local_rag:
        if not _RAG_INDEX.exists() or not _CHUNKS.exists():
            # 本地文献是可选增强：库为空时继续真实运行，由开放文献或 needs_data 接手。
            # 绝不能为了满足 preflight 而回退检索题源 sjtu-booklet.pdf。
            warnings.append("用户本地文献库为空；Local RAG 将跳过，sjtu-booklet.pdf 不会作为证据。")

    # 7) DeepResearch 配置
    if use_deep_research:
        dr_ok = getattr(s, "deep_research_configured", None)
        if dr_ok is None:
            dr_base = (getattr(s, "dashscope_deep_research_base_url", "") or "").strip()
            dr_ok = bool(dr_base) and _WORKSPACE_PLACEHOLDER not in dr_base and bool(
                (getattr(s, "dashscope_api_key", "") or "").strip()
            )
        if not dr_ok:
            warnings.append("DeepResearch 未完整配置；可禁用 DeepResearch 后重试，或配置 WORKSPACE_ID")
        try:
            assert_qwen_model(getattr(s, "qwen_deep_research_model", "qwen-deep-research"))
        except ValueError as exc:
            warnings.append(f"DeepResearch 模型配置异常：{exc}")

    # 8) OpenAlex 可选
    if not (getattr(s, "openalex_api_key", "") or "").strip():
        warnings.append("OpenAlex Key 未配置（可选，不阻塞真实模式）")

    # 9) Actual network/auth/model probe only when the user starts a real run.
    # The passive banner keeps this False to avoid a paid call on every rerender.
    if check_connectivity and not errors:
        connectivity["checked"] = True
        try:
            from app.clients.qwen_chat_client import QwenChatClient

            probe = QwenChatClient(s).probe(getattr(s, "qwen_fast_model", None))
            connectivity.update({"ok": True, "model": probe.get("model")})
        except Exception as exc:
            detail = str(exc)
            connectivity.update({"ok": False, "error": detail})
            errors.append(f"百炼连通性检查失败：{detail}")
            if "OUTBOUND_HTTPS_PROXY" in detail or "HTTPS" in detail or "网络" in detail:
                fix_commands.append("检查 VPN/防火墙，或在 .env 配置 OUTBOUND_HTTPS_PROXY")

    # 去重 fix_commands
    fix_commands = list(dict.fromkeys(fix_commands))
    ok = len(errors) == 0
    return {
        "ok": ok,
        "errors": errors,
        "warnings": warnings,
        "fix_commands": fix_commands,
        "can_run_real": ok,
        "can_run_mock": True,
        "connectivity": connectivity,
    }
