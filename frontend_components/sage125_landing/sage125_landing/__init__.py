# Copyright (c) 2026 SAGE125 AI Scientist Team.
#
# 首页只挂载一次 Custom Component v2：Hero + 统计卡 + Bento。

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional

import streamlit as st
from streamlit.components.v2.get_bidi_component_manager import get_bidi_component_manager
from streamlit.components.v2.manifest_scanner import ComponentConfig, ComponentManifest

_COMPONENT_KEY = "sage125-landing.sage125_landing"
_SCROLL_KEY = "sage125-landing.sage125_scroll"
_PACKAGE_ROOT = Path(__file__).resolve().parent
_ASSET_DIR = _PACKAGE_ROOT / "frontend" / "build"


def _ensure_declared_asset_root() -> None:
    """AppTest / 未扫描到已安装包时，仍按本包 pyproject 声明绑定 asset_dir。"""
    manager = get_bidi_component_manager()
    handler = manager._manifest_handler
    if handler.get_asset_root(_COMPONENT_KEY) is not None and handler.get_asset_root(_SCROLL_KEY) is not None:
        return
    handler.process_manifest(
        ComponentManifest(
            name="sage125-landing",
            version="0.1.0",
            components=[
                ComponentConfig(name="sage125_landing", asset_dir="frontend/build"),
                ComponentConfig(name="sage125_scroll", asset_dir="frontend/build"),
            ],
        ),
        _PACKAGE_ROOT,
    )


_ensure_declared_asset_root()
_mount = st.components.v2.component(
    _COMPONENT_KEY,
    js="index-*.js",
    css="index-*.css",
    html='<div class="sage125-landing-root"></div>',
    isolate_styles=False,
)
_scroll_mount = st.components.v2.component(
    _SCROLL_KEY,
    js="scroll.js",
    html='<div class="sage125-scroll-root"></div>',
    isolate_styles=False,
)


def _noop_callback(*_args: Any, **_kwargs: Any) -> None:
    return None


def sage125_landing(
    *,
    q028_available: bool = False,
    question_count: Optional[int] = None,
    evidence_count: Optional[int] = None,
    plan_count: Optional[int] = None,
    coverage: Optional[float] = None,
    coverage_status: Optional[str] = None,
    stats_status: str = "loading",
    on_enter_workspace: Optional[Callable[[], None]] = None,
    on_view_q028: Optional[Callable[[], None]] = None,
    key: Optional[str] = None,
) -> dict:
    data = {
        "q028_available": bool(q028_available),
        "question_count": question_count,
        "evidence_count": evidence_count,
        "plan_count": plan_count,
        "coverage": coverage,
        "coverage_status": coverage_status,
        "stats_status": stats_status,
    }
    return _mount(
        key=key or "sage125-landing-home-v2",
        data=data,
        on_enter_workspace_change=on_enter_workspace or _noop_callback,
        on_view_q028_change=on_view_q028 or _noop_callback,
    )


def sage125_scroll(
    *,
    scroll_target: Optional[str] = None,
    nonce: Optional[str] = None,
    on_acknowledged: Optional[Callable[[], None]] = None,
    key: Optional[str] = None,
) -> dict:
    return _scroll_mount(
        key=key or "sage125-scroll-trigger",
        data={"scrollTarget": scroll_target, "nonce": nonce},
        on_acknowledged_change=on_acknowledged or _noop_callback,
    )


__all__ = ["sage125_landing", "sage125_scroll"]
