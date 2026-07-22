"""
app.ui.theme —— 前端主题变量（颜色、领域配色、Agent 状态配色、字体）。

集中定义“科研发现控制台”视觉体系，供 components / charts / style 复用，
保证配色与赛题 12 领域一致，避免在各处散落魔法值。
"""

from __future__ import annotations

# ---- 应用标题 ----
APP_TITLE = "SAGE125 AI Scientist"
APP_SUBTITLE = "From 125 Questions to Verifiable Scientific Hypotheses"
APP_TITLE_ZH = "SAGE125 AI Scientist：科学假设生成与研究计划设计"

# ---- 基础配色 ----
BG_DARK = "#07111F"
BG_PANEL = "#0B1628"
CARD_BG = "rgba(255, 255, 255, 0.92)"
CARD_BG_DARK = "rgba(15, 23, 42, 0.82)"
PRIMARY_BLUE = "#2563EB"
SCIENCE_CYAN = "#06B6D4"
SJTU_RED = "#B91C1C"
GOLD = "#F59E0B"
TEXT_DARK = "#0F172A"
TEXT_MUTED = "#64748B"
BORDER = "rgba(148, 163, 184, 0.35)"
SUCCESS = "#10B981"
WARNING = "#F59E0B"
DANGER = "#EF4444"

# ---- 12 个领域配色（与 extract_125_questions 的标准领域一致）----
DOMAIN_COLORS: dict[str, str] = {
    "Mathematical Sciences": "#16A34A",
    "Chemistry": "#BE185D",
    "Medicine & Health": "#3730A3",
    "Biology": "#92400E",
    "Astronomy": "#86198F",
    "Physics": "#C026D3",
    "Engineering & Materials Science": "#475569",
    "Information Science": "#DC2626",
    "Neuroscience": "#DB2777",
    "Ecology": "#0F766E",
    "Energy Science": "#A16207",
    "Artificial Intelligence": "#0369A1",
}

# ---- Agent 状态配色 ----
AGENT_STATUS_COLORS: dict[str, str] = {
    "pending": "#94A3B8",    # gray
    "running": PRIMARY_BLUE,  # blue
    "completed": SUCCESS,     # green
    "failed": DANGER,         # red
    "skipped": WARNING,       # amber
}

# ---- 证据来源配色（用于分布图与 badge）----
SOURCE_COLORS: dict[str, str] = {
    "booklet": "#2563EB",
    "rag": "#06B6D4",
    "deep_research": "#8B5CF6",
    "arxiv": "#B91C1C",
    "crossref": "#0F766E",
    "openalex": "#A16207",
    "user_upload": "#475569",
}

# ---- 字体（不依赖外部字体文件）----
FONT_STACK = (
    '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Inter", '
    '"PingFang SC", "Microsoft YaHei", system-ui, sans-serif'
)
MONO_STACK = 'Menlo, Monaco, Consolas, "Courier New", monospace'

# 校验状态到展示颜色的映射。
STATUS_COLORS: dict[str, str] = {
    "draft": TEXT_MUTED,
    "needs_data": WARNING,
    "ready_for_validation": PRIMARY_BLUE,
    "validated": SUCCESS,
}


def domain_color(domain: str) -> str:
    """
    返回领域对应的主题色（未知领域回退为主蓝）。

    参数：
        domain: 领域名称。

    返回：
        十六进制颜色字符串。
    """
    # 未收录的领域统一回退主蓝，避免 KeyError。
    return DOMAIN_COLORS.get(domain, PRIMARY_BLUE)


def status_color(status: str) -> str:
    """
    返回校验状态对应的展示颜色。

    参数：
        status: validation_status 值。

    返回：
        十六进制颜色字符串。
    """
    # 未知状态回退为静默灰。
    return STATUS_COLORS.get(status, TEXT_MUTED)
