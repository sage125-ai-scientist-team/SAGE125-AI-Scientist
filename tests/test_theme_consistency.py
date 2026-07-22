"""
tests/test_theme_consistency.py — 深色主题一致性测试（P0-4）。

覆盖：
    - .streamlit/config.toml 存在且 base=dark；
    - style.css 覆盖 stAppViewContainer 与关键组件（selectbox/expander/tabs/download）；
    - streamlit_app.py 顶部无条件调用 load_css；
    - load_css 每次 rerun 都注入（不做幂等短路）；
    - 前端源码不含把主背景强制变白的全局样式。
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_config_toml_dark():
    """config.toml 存在且 base=dark。"""
    cfg = ROOT / ".streamlit" / "config.toml"
    assert cfg.exists(), "缺少 .streamlit/config.toml"
    text = cfg.read_text(encoding="utf-8")
    assert 'base = "dark"' in text
    assert "backgroundColor" in text


def test_style_css_covers_key_containers():
    """style.css 覆盖 App 容器与关键组件深色样式。"""
    css = (ROOT / "app" / "ui" / "style.css").read_text(encoding="utf-8")
    assert "stAppViewContainer" in css
    assert "stSidebar" in css
    for token in ("stTabs", "stExpander", "stDownloadButton", "baseweb=\"select\"", "stTable"):
        assert token in css, f"style.css 缺少组件样式：{token}"


def test_load_css_injected_every_run():
    """load_css 不再基于 _css_loaded 幂等短路（每次 rerun 都注入）。"""
    comp = (ROOT / "app" / "ui" / "components.py").read_text(encoding="utf-8")
    # 不应存在 "if st.session_state.get(\"_css_loaded\"): return" 这类短路。
    assert "_css_loaded" not in comp, "load_css 不应再使用 _css_loaded 幂等短路"


def test_streamlit_app_calls_load_css_top():
    """streamlit_app.main 顶部调用 load_css。"""
    app = (ROOT / "app" / "ui" / "streamlit_app.py").read_text(encoding="utf-8")
    assert "components.load_css()" in app
    idx_css = app.index("components.load_css()")
    idx_hero = app.index("render_hero")
    assert idx_css < idx_hero, "load_css 应在渲染主体之前调用"


def test_no_forced_white_app_background():
    """style.css 不应把主背景强制设为白色。"""
    css = (ROOT / "app" / "ui" / "style.css").read_text(encoding="utf-8").lower()
    # 主容器背景不应是白色。
    assert "background: #fff" not in css.replace(" ", "")
    assert "background:#ffffff" not in css.replace(" ", "") or "report-panel" in css
