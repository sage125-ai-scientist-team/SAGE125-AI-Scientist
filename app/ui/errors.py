"""
app.ui.errors —— 前端用户级错误显示策略（完整契约）。

原则：
    - 主界面只显示简短、可操作的错误 + 修复命令；
    - traceback 仅放在默认折叠的「技术细节」expander；
    - 所有文本经 mask_sensitive_text 脱敏，绝不显示 API Key / .env 全文。

本模块对外 API 必须与 streamlit_app.py / components.py 中的 errors.xxx 调用一一对应，
禁止出现 AttributeError。
"""

from __future__ import annotations

import re
import traceback
from typing import Optional

import streamlit as st

from app.ui.key_factory import make_widget_key

# 默认真实模式失败修复命令。
_DEFAULT_REAL_FIX = [
    "py -3 scripts/doctor.py --real-check",
    "py -3 scripts/smoke_bailian.py --chat",
    "py -3 scripts/smoke_bailian.py --embedding",
    "py -3 scripts/build_rag_index.py",
]

# 脱敏正则：sk- Key、常见 env 赋值、长 hex token。
_SK_PATTERN = re.compile(r"sk-[A-Za-z0-9._-]{6,}", re.IGNORECASE)
_ENV_KEY_PATTERN = re.compile(
    r"(DASHSCOPE_API_KEY|OPENALEX_API_KEY|WORKSPACE_ID)\s*[=:]\s*[^\s\n\r\"']+",
    re.IGNORECASE,
)


def mask_sensitive_text(text: str) -> str:
    """
    对错误文本做脱敏：隐藏 sk- Key、env 赋值、疑似长 token。

    参数：
        text: 原始文本。

    返回：
        脱敏后的安全字符串。
    """
    if not text:
        return ""
    out = str(text)
    out = _SK_PATTERN.sub("sk-****MASKED", out)
    out = _ENV_KEY_PATTERN.sub(r"\1=****MASKED", out)
    return out


def safe_exception_text(error: str | Exception) -> str:
    """
    将异常转为脱敏后的可读字符串（含 traceback，供技术细节 expander）。

    参数：
        error: 异常对象或字符串。

    返回：
        脱敏后的错误文本。
    """
    if isinstance(error, BaseException):
        raw = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    else:
        raw = str(error)
    return mask_sensitive_text(raw)


def render_user_error(
    title: str,
    message: str,
    fix_commands: Optional[list[str]] = None,
    details: str | Exception | None = None,
    severity: str = "error",
    key: str | None = None,
    *,
    key_ns: str | None = None,
) -> None:
    """
    渲染统一的用户级错误卡（简短错误 + 修复命令 + 可折叠技术细节）。

    参数：
        title:        错误标题。
        message:      面向用户的简短说明。
        fix_commands: 建议在本地终端运行的修复命令。
        details:      技术细节（traceback 等），默认折叠。
        severity:     error | warning | info。
        key:          expander 唯一 key 命名空间。
        key_ns:       向后兼容别名（等同 key）。
    """
    ns = key or key_ns or "err"
    icon = {"error": "⛔", "warning": "⚠️", "info": "ℹ️"}.get(severity, "⛔")
    border = {"error": "#F87171", "warning": "#FBBF24", "info": "#22D3EE"}.get(severity, "#F87171")
    st.markdown(
        f"""<div class="user-error-card" style="border-left:4px solid {border}">
            <div class="ue-title">{icon} {mask_sensitive_text(title)}</div>
            <div class="ue-message">{mask_sensitive_text(message)}</div>
        </div>""",
        unsafe_allow_html=True,
    )
    if fix_commands:
        st.markdown('<div class="ue-fix-label">建议修复（在本地终端运行）：</div>', unsafe_allow_html=True)
        for cmd in fix_commands:
            st.code(cmd, language="powershell")
    if details is not None:
        with st.expander("技术细节（默认折叠，已脱敏）", expanded=False):
            st.caption("以下为内部调试信息，不含 API Key。")
            st.code(safe_exception_text(details))


def run_failed(
    error: str | Exception,
    run_id: str | None = None,
    fix_commands: list[str] | None = None,
    details: str | Exception | None = None,
    *,
    error_type: str | None = None,
    mode: str = "mock",
) -> None:
    """
    渲染「AI Scientist 运行失败」标准错误卡。

    参数：
        error:        错误摘要或异常对象。
        run_id:       失败运行的 ID（如有）。
        fix_commands: 自定义修复命令；缺省按 mode 推断。
        details:      技术细节（默认从 error 提取 traceback）。
        error_type:   错误类型标记（如 read_timeout）。
        mode:         mock | real，影响默认修复命令。
    """
    if error_type == "read_timeout":
        run_timeout(recovered_run_id=run_id)
        return

    err_text = safe_exception_text(error) if isinstance(error, BaseException) else mask_sensitive_text(str(error))
    msg_parts = ["AI Scientist 运行未能完成。"]
    if run_id:
        msg_parts.append(f"run_id：{run_id}")
    msg_parts.append(f"原因：{err_text[:500]}")
    msg_parts.append(
        "可能原因：百炼 API 未配置/未授权、网络超时、RAG 索引缺失、或 DeepResearch 长任务失败。"
        if mode == "real"
        else "可能原因：问题清单缺失或本地索引异常。"
    )

    cmds = fix_commands
    if cmds is None:
        cmds = list(_DEFAULT_REAL_FIX) if mode == "real" else None
        low = err_text.lower()
        if mode == "real":
            if "未通过" in err_text and "校验" in err_text:
                cmds = [
                    "# 模型 JSON 不完整：请重启 Streamlit 后重试（已修复 pipeline 上下文）",
                    "py -3 scripts/check_real_qwen_invocation.py --question-id Q001 --no-deepresearch",
                ]
                msg_parts[-1] = (
                    "可能原因：某 Agent 返回的 JSON 缺少必填字段（如 technical_details），"
                    "或模型回显了输入而非输出 schema。请重启 Streamlit 使最新代码生效后重试。"
                )
            elif "dashscope" in low or "api key" in low or "401" in low or "403" in low:
                cmds = ["py -3 scripts/setup_env.py", "py -3 scripts/smoke_bailian.py --chat"]
            elif "connection" in low or "10061" in low:
                cmds = ["uvicorn app.api.main:app --reload --port 8000"]
            elif "timeout" in low or "timed out" in low:
                cmds = [
                    "# 可先关闭 DeepResearch 后重试",
                    "py -3 scripts/smoke_bailian.py --chat",
                    "py -3 scripts/check_real_qwen_invocation.py --question-id Q001 --no-deepresearch",
                ]

    render_user_error(
        title="AI Scientist 运行失败",
        message=" ".join(msg_parts),
        fix_commands=cmds,
        details=details if details is not None else error,
        key_ns="run_fail",
    )


def run_timeout(recovered_run_id: str | None = None) -> None:
    """Pipeline HTTP 读超时（真实模式通常需 15–25 分钟）。"""
    msg = (
        "真实模式运行超时。Pipeline 含多次 Qwen 调用，通常需 15–25 分钟。"
        "可先关闭 DeepResearch 或运行 smoke_bailian 检查百炼链路。"
    )
    if recovered_run_id:
        msg += f" 系统已在本地找到可能已完成的运行：{recovered_run_id}。"
    else:
        msg += " 若后端仍在运行，请稍后点击「加载历史运行」查看结果。"
    render_user_error(
        title="运行超时（非配置错误）",
        message=msg,
        fix_commands=[
            "py -3 scripts/smoke_bailian.py --chat",
            "py -3 scripts/check_real_qwen_invocation.py --question-id Q001 --no-deepresearch",
            "$env:FRONTEND_RUN_TIMEOUT_SECONDS='2400'",
        ],
        severity="warning",
        key_ns="run_timeout",
    )


def api_disconnected(
    api_base_url: str | None = None,
    details: str | Exception | None = None,
) -> None:
    """API 未连接。"""
    base = mask_sensitive_text(api_base_url or "http://localhost:8000")
    render_user_error(
        title="后端 API 未连接",
        message=f"未检测到本地 FastAPI 服务（{base}）。模拟模式可使用进程内回退；真实模式建议先启动 API。",
        fix_commands=["uvicorn app.api.main:app --reload --port 8000"],
        details=details,
        key_ns="api_disc",
    )


def qwen_not_configured(details: str | Exception | None = None) -> None:
    """Qwen / 百炼未配置。"""
    render_user_error(
        title="Qwen / 百炼未配置",
        message="真实模式需要在本地 .env 配置 DASHSCOPE_API_KEY 与 WORKSPACE_ID。前端不会读取或显示你的 Key。",
        fix_commands=["py -3 scripts/setup_env.py", "py -3 scripts/smoke_bailian.py --chat"],
        details=details,
        key_ns="qwen_cfg",
    )


def questions_missing(details: str | Exception | None = None) -> None:
    """
    渲染「125 问题清单缺失」错误卡，阻止静默空跑。

    参数：
        details: 可选技术细节（已走统一脱敏路径）。

    返回：
        None。副作用是在 Streamlit 页面渲染错误卡与修复命令。
    """
    render_user_error(
        title="问题清单未加载",
        message=(
            "当前没有可用的 125 问题清单，因此无法选题，也无法启动 Mock / Real 运行。"
            "请先生成 data/processed/questions_125.json；Preview 环境可启用 bootstrap 种子。"
        ),
        fix_commands=[
            "py -3 scripts/extract_125_questions.py",
            "py -3 scripts/bootstrap_preview_data.py --allow-seed",
        ],
        details=details,
        key_ns="questions_missing",
    )


def question_not_selected(details: str | Exception | None = None) -> None:
    """
    渲染「尚未选择科学问题」错误卡，避免按钮点击无反馈。

    参数：
        details: 可选技术细节（例如 preset 关键词未命中）。

    返回：
        None。副作用是在 Streamlit 页面渲染错误卡与修复建议。
    """
    render_user_error(
        title="尚未选择科学问题",
        message=(
            "请先在 STEP 01 选择一个问题，或点击侧栏 Demo Presets。"
            "未选题时系统不会启动流水线，也不会写入运行产物。"
        ),
        fix_commands=[
            "py -3 scripts/extract_125_questions.py",
            "py -3 scripts/bootstrap_preview_data.py --allow-seed",
        ],
        details=details,
        severity="warning",
        key_ns="question_not_selected",
    )


def rag_missing(details: str | Exception | None = None) -> None:
    """RAG 索引缺失。"""
    render_user_error(
        title="RAG 索引未构建",
        message="真实模式启用 Local RAG 时需要向量索引；模拟模式可跳过。",
        fix_commands=["py -3 scripts/build_rag_index.py"],
        details=details,
        key_ns="rag_missing",
    )


def report_mismatch(
    selected_question: str,
    report_question: str,
    run_id: str | None = None,
) -> None:
    """报告与所选问题不一致：阻断展示。"""
    extra = f"（run_id={run_id}）" if run_id else ""
    render_user_error(
        title="当前报告不属于所选问题",
        message=(
            f"你当前选择的问题是：「{selected_question}」，"
            f"但该运行结果对应的问题是：「{report_question}」{extra}。"
            "为避免串线，系统已阻断展示。请重新为当前问题运行，或切换到对应的历史运行。"
        ),
        key_ns="report_mismatch",
    )


def render_report_mismatch(
    selected_question: str,
    plan_question: str,
    on_fix_key: str = "mismatch",
) -> None:
    """向后兼容别名：render_report_mismatch -> report_mismatch。"""
    report_mismatch(selected_question, plan_question, run_id=None)


def missing_artifact(file_name: str, run_id: str | None = None) -> None:
    """运行产物文件缺失。"""
    rid = f"（run_id={run_id}）" if run_id else ""
    render_user_error(
        title="运行产物缺失",
        message=f"未找到文件 `{file_name}` {rid}。请重新运行或加载其他历史运行。",
        fix_commands=["py -3 scripts/run_demo.py --question-id Q001"] if not run_id else None,
        severity="warning",
        key_ns=make_widget_key("missing_art", run_id or "na", file_name),
    )


def unexpected_error(
    title: str,
    error: str | Exception,
    fix_commands: list[str] | None = None,
) -> None:
    """组件局部渲染失败时的兜底错误卡。"""
    render_user_error(
        title=title,
        message=safe_exception_text(error)[:400],
        fix_commands=fix_commands,
        details=error,
        key_ns="unexpected",
    )
