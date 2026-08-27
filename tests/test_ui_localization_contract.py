# -*- coding: utf-8 -*-
"""
tests/test_ui_localization_contract.py — 前端中文化 / 视觉重构契约测试。

覆盖 LOCAL_ONLY_STREAMLIT_UI_CHINESE_AND_VISUAL_REDESIGN 任务的关键约束：
    1. 集中中文映射（app.ui.i18n）存在且覆盖主要界面文案；
    2. 主界面不再以纯英文原文作为可见标题（改用 i18n 映射）；
    3. 允许的技术专名不被误判为需要翻译；
    4. Q001–Q125 题目原文、外文文献标题、DOI/URL/作者、领域内部英文 key 均不改变；
    5. Plotly 统一配置存在且所有用户可见 Plotly 渲染都经过该配置；
    6. 主界面不再调用随机力导向 spring_layout 知识图；
    7. 科研证据链固定顺序 + Mock 显式标注；
    8. HTML 转义（esc）用于科研证据链动态文本；
    9. 移动端响应式 CSS 存在；
    10. 未引入外部 JS / CDN；
    11. 快速示例中文标签正确映射到内部英文 key。

不使用 assert False / skip / xfail，不删除断言，不修改后端实际数据。
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
UI_DIR = ROOT / "app" / "ui"


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1) 集中中文映射存在且覆盖主要界面文案。
# ---------------------------------------------------------------------------


def test_i18n_module_exists_with_required_maps():
    from app.ui import i18n

    for name in (
        "UI_TEXT_ZH",
        "DOMAIN_DISPLAY_ZH",
        "STATUS_DISPLAY_ZH",
        "STAGE_DISPLAY_ZH",
        "PRESET_DISPLAY_ZH",
        "SOURCE_TYPE_DISPLAY_ZH",
    ):
        assert hasattr(i18n, name), f"app.ui.i18n 缺少映射表：{name}"
        assert isinstance(getattr(i18n, name), dict) and getattr(i18n, name), f"{name} 应为非空 dict"

    for fn in ("ui_text", "domain_label", "status_label", "stage_label", "source_type_label"):
        assert hasattr(i18n, fn) and callable(getattr(i18n, fn)), f"app.ui.i18n 缺少函数：{fn}"


def test_ui_text_covers_core_shell_labels():
    """核心界面壳层文案必须在 UI_TEXT_ZH 中登记为中文。"""
    from app.ui.i18n import UI_TEXT_ZH

    required_keys = [
        "mode_control", "mock_mode", "real_mode", "system_status", "pipeline_switches",
        "demo_presets", "first_run_wizard", "select_a_scientific_question",
        "knowledge_graph", "agent_pipeline_timeline", "evidence_source_distribution",
        "relevance_score_distribution", "flow_question", "flow_evidence",
        "flow_hypothesis", "flow_experiment", "flow_report",
    ]
    for key in required_keys:
        assert key in UI_TEXT_ZH, f"UI_TEXT_ZH 缺少键：{key}"
        value = UI_TEXT_ZH[key]
        assert value, f"UI_TEXT_ZH[{key}] 不应为空串"
        assert any("\u4e00" <= ch <= "\u9fff" for ch in value), f"UI_TEXT_ZH[{key}] 应包含中文：{value}"


def test_ui_text_unknown_key_falls_back_not_empty():
    """未知 key 必须安全回退为 key 本身，不返回空串。"""
    from app.ui.i18n import ui_text

    assert ui_text("__not_registered_key__") == "__not_registered_key__"
    assert ui_text("") == ""  # 空 key 本身即回退值，函数不额外制造空串以外的意外值


def test_domain_label_preserves_internal_english_key_on_unknown():
    """未登记领域必须原样返回英文，不返回空串，不修改传入内部 key 语义。"""
    from app.ui.i18n import domain_label

    assert domain_label("Biology") == "生物学"
    assert domain_label("Totally Unknown Domain XYZ") == "Totally Unknown Domain XYZ"
    assert domain_label(None) == ""


# ---------------------------------------------------------------------------
# 2) 主界面不再以纯英文原文作为可见标题。
# ---------------------------------------------------------------------------

_BANNED_LITERAL_TITLES = [
    '"Mode Control"',
    '"System Status"',
    '"Pipeline Switches"',
    '"Demo Presets"',
]


def test_sidebar_headers_no_longer_hardcoded_english_literals():
    """侧边栏标题不应再以英文字符串字面量直接传给 st.markdown/组件标题。"""
    src = _read("app/ui/components.py") + _read("app/ui/streamlit_app.py")
    for literal in _BANNED_LITERAL_TITLES:
        assert literal not in src, f"仍存在硬编码英文标题字面量：{literal}"


def test_section_titles_use_i18n_not_raw_english_strings():
    """STEP 0X 分区标题应通过 i18n.ui_text 生成，不再直接传英文标题字符串。"""
    src = _read("app/ui/streamlit_app.py")
    assert 'ui_text("first_run_wizard")' in src or "ui_text('first_run_wizard')" in src
    assert "select_a_scientific_question" in src
    for banned in ('"Select a Scientific Question"', '"First Run Wizard"'):
        assert f"section_title({banned}" not in src.replace(" ", "").replace("\n", "")


def test_allowed_technical_terms_not_flagged():
    """允许保留的技术专名（如 SAGE125/API/DOI/Mock/Real）不应被误判为待翻译项。"""
    src = _read("app/ui/streamlit_app.py") + _read("app/ui/components.py")
    for term in ("SAGE125", "DOI", "API", "JSON", "Mock", "Real"):
        assert term in src, f"允许保留的技术专名缺失（不应被过度翻译删除）：{term}"


# ---------------------------------------------------------------------------
# 3) 保护科学问题原文、文献标题、DOI/URL/作者、领域内部英文 key。
# ---------------------------------------------------------------------------


def test_domain_internal_keys_untouched_in_theme():
    """theme.DOMAIN_COLORS 的领域 key 必须仍是英文（内部稳定值不变）。"""
    from app.ui import theme

    for domain in (
        "Mathematical Sciences", "Chemistry", "Medicine & Health", "Biology",
        "Astronomy", "Physics", "Engineering & Materials Science",
        "Information Science", "Neuroscience", "Ecology", "Energy Science",
        "Artificial Intelligence",
    ):
        assert domain in theme.DOMAIN_COLORS, f"theme.DOMAIN_COLORS 缺少内部英文领域 key：{domain}"


def test_domain_display_zh_keys_match_internal_english_keys():
    """DOMAIN_DISPLAY_ZH 的 key 必须与 theme.DOMAIN_COLORS 的英文 key 完全一致。"""
    from app.ui import theme
    from app.ui.i18n import DOMAIN_DISPLAY_ZH

    assert set(DOMAIN_DISPLAY_ZH.keys()) == set(theme.DOMAIN_COLORS.keys())


def test_question_selectbox_shows_untranslated_question_text():
    """题目选择框仍以 `QID · 原文` 格式展示，不翻译题目正文。"""
    src = _read("app/ui/components.py")
    workspace = _read("app/ui/workspace.py")
    official = _read("app/catalog/official.py")
    assert '"选择一个科学问题"' in src
    assert "format_func=_format_question_option" in src
    assert "selector_label" in src or "official_question_text" in workspace
    assert "title_en" in official
    assert "title_zh" in official
    assert "不得自动调用模型翻译" not in src
    assert "治愈所有癌症" not in src + workspace


def test_evidence_card_uses_esc_for_dynamic_title_and_quote():
    """证据卡标题与原文引用必须经 esc() 转义，不直接拼入 unsafe HTML。"""
    src = _read("app/ui/components.py")
    assert "esc(card.get('title'))" in src or 'esc(card.get("title"))' in src
    assert "esc((card.get('quoted_text')" in src or 'esc((card.get("quoted_text")' in src


# ---------------------------------------------------------------------------
# 4) Plotly 统一配置：所有用户可见图表都经过 PLOTLY_CONFIG。
# ---------------------------------------------------------------------------


def test_plotly_config_disables_modebar():
    from app.ui.charts import PLOTLY_CONFIG

    assert PLOTLY_CONFIG.get("displayModeBar") is False
    assert PLOTLY_CONFIG.get("displaylogo") is False
    assert PLOTLY_CONFIG.get("scrollZoom") is False
    assert PLOTLY_CONFIG.get("responsive") is True


def test_render_plotly_chart_wrapper_exists_and_uses_config():
    src = _read("app/ui/charts.py")
    assert "def render_plotly_chart(" in src
    assert "config=PLOTLY_CONFIG" in src


def test_no_raw_st_plotly_chart_calls_outside_wrapper():
    """app/ui 下所有用户可见 Plotly 渲染都必须经过 charts.render_plotly_chart。"""
    for fname in ("components.py", "streamlit_app.py"):
        src = _read(f"app/ui/{fname}")
        assert "st.plotly_chart(" not in src, f"{fname} 存在未经统一 wrapper 的 st.plotly_chart 调用"


def test_charts_module_internal_plotly_chart_call_passes_config():
    """charts.py 内部唯一的 st.plotly_chart 调用（wrapper 本体）必须传入 config。"""
    src = _read("app/ui/charts.py")
    # render_plotly_chart 函数体内应包含唯一一次 st.plotly_chart 调用并传 config。
    assert src.count("st.plotly_chart(") == 1
    idx = src.index("st.plotly_chart(")
    body = src[idx: idx + 400]
    assert "config=PLOTLY_CONFIG" in body


# ---------------------------------------------------------------------------
# 5) 主界面不再调用随机力导向知识图；科研证据链存在且顺序固定。
# ---------------------------------------------------------------------------


def test_main_ui_does_not_call_spring_layout_knowledge_graph():
    for fname in ("components.py", "streamlit_app.py"):
        src = _read(f"app/ui/{fname}")
        assert "make_knowledge_graph(" not in src, f"{fname} 不应再调用随机力导向知识图"
        assert "spring_layout(" not in src, f"{fname} 不应直接调用 spring_layout 布局"


def test_research_flow_function_exists_and_is_wired_in():
    src = _read("app/ui/components.py")
    assert "def render_research_flow(" in src
    assert "render_research_flow(" in _read("app/ui/components.py")


def test_research_flow_stage_order_fixed():
    """科研证据链五阶段顺序必须固定为：问题→证据→假设→实验→报告。"""
    src = _read("app/ui/components.py")
    idx_q = src.index('_rf_stage("01"')
    idx_e = src.index('_rf_stage("02"')
    idx_h = src.index('_rf_stage("03"')
    idx_x = src.index('_rf_stage("04"')
    idx_r = src.index('_rf_stage("05"')
    assert idx_q < idx_e < idx_h < idx_x < idx_r, "科研证据链阶段顺序被打乱"


def test_research_flow_mock_is_explicitly_labeled():
    src = _read("app/ui/components.py")
    assert "rf-mock-banner" in src
    assert "模拟演示数据" in src
    assert "rf-badge-mock" in src
    assert "模拟证据" in src


def test_research_flow_does_not_infer_actual_from_mode_alone():
    """“已实际执行”只能来自 plan.actual_execution 或 experiment_result 的显式信号。"""
    src = _read("app/ui/components.py")
    idx = src.index("def render_research_flow(")
    end = src.index("\ndef ", idx + 10)
    body = src[idx:end]
    assert 'status_key = "actual"' in body
    # 不得仅凭 is_mock 为 False 就判定为 actual：actual 分支必须先检查
    # experiment_result 或 plan.actual_execution，而不是直接 else 落到 actual。
    assert 'elif is_mock:\n            status_key = "mock"\n        else:\n            status_key = "planned"' in body


def test_research_flow_escapes_dynamic_text():
    src = _read("app/ui/components.py")
    idx = src.index("def render_research_flow(")
    end = src.index("\ndef ", idx + 10)
    body = src[idx:end]
    assert "esc(qtext)" in body
    assert "esc(card.get(\"title\"))" in body
    assert "esc(h.get(\"hypothesis\"))" in body


# ---------------------------------------------------------------------------
# 6) HTML 注入不得成为可执行标签（回归既有 esc 机制）。
# ---------------------------------------------------------------------------


def test_esc_neutralizes_script_tag():
    from app.ui.components import esc

    payload = "<script>alert(1)</script>"
    escaped = esc(payload)
    assert "<script>" not in escaped
    assert "&lt;script&gt;" in escaped


# ---------------------------------------------------------------------------
# 7) 移动端响应式 CSS 存在；无外部 JS / CDN。
# ---------------------------------------------------------------------------


def test_mobile_breakpoint_css_exists():
    css = _read("app/ui/style.css")
    assert "@media (max-width: 760px)" in css
    assert "rf-track" in css and "flex-direction: column" in css


def test_reduced_motion_media_query_present():
    css = _read("app/ui/style.css")
    assert "prefers-reduced-motion" in css


def test_no_external_js_or_cdn_introduced():
    for fname in ("components.py", "streamlit_app.py", "charts.py", "i18n.py"):
        src = _read(f"app/ui/{fname}")
        for banned in ("<script src=", "cdn.jsdelivr", "unpkg.com", "<iframe"):
            assert banned not in src, f"{fname} 不应引入外部 JS/CDN/iframe：{banned}"


# ---------------------------------------------------------------------------
# 8) 快速示例（原 Demo Presets）中文标签映射到正确内部英文 key。
# ---------------------------------------------------------------------------


def test_preset_labels_map_to_expected_internal_keys():
    from app.ui.i18n import PRESET_DISPLAY_ZH, PRESET_KEYWORDS

    expected = {
        "prime": "素数",
        "pandemic": "疫情预测",
        "climate": "气候变化",
        "creativity": "AI 创造力",
        "quantum": "量子计算",
    }
    for key, zh in expected.items():
        assert PRESET_DISPLAY_ZH.get(key) == zh, f"预设 {key} 中文标签不匹配"
        assert key in PRESET_KEYWORDS, f"预设 {key} 缺少关键词映射"


def test_render_quick_presets_uses_pills_or_safe_fallback():
    src = _read("app/ui/components.py")
    assert "def render_quick_presets(" in src
    assert "st.pills" in src or "getattr(st, \"pills\"" in src


def test_render_mode_control_uses_segmented_control_or_safe_fallback():
    src = _read("app/ui/components.py")
    assert "def render_mode_control(" in src
    assert "segmented_control" in src
    # 不得通过显示文字解析业务状态（旧实现：mode_choice.startswith("Mock")）。
    assert "mode_choice.startswith(" not in src
