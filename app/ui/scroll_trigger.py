# -*- coding: utf-8 -*-
"""一次性滚动 Trigger：选题目 / 选完后回到研究概览。

优先复用已安装的 Streamlit Custom Components v2；不可用时回退到
``st.components.v1.html``，在父文档上执行一次 scrollIntoView。
"""

from __future__ import annotations

import json
import time
from typing import Any

import streamlit as st
import streamlit.components.v1 as components_v1

SCROLL_TARGET_KEY = "sage125_scroll_target"
SCROLL_NONCE_KEY = "sage125_scroll_nonce"
PICKER_FOCUS_KEY = "question_picker_focus"

_ALLOWED = {"question-picker", "research-overview"}


def request_scroll(target: str) -> None:
    if target not in _ALLOWED:
        return
    st.session_state[SCROLL_TARGET_KEY] = target
    st.session_state[SCROLL_NONCE_KEY] = str(time.time_ns())


def consume_scroll_target() -> tuple[str | None, str | None]:
    target = st.session_state.get(SCROLL_TARGET_KEY)
    nonce = st.session_state.get(SCROLL_NONCE_KEY)
    st.session_state[SCROLL_TARGET_KEY] = None
    return (str(target) if target in _ALLOWED else None), (str(nonce) if nonce else None)


def request_question_picker(*, switch_page: Any | None = None) -> None:
    """未选题按钮：已在合并页则滚动；否则切到科学问题页再滚动。"""
    st.session_state[PICKER_FOCUS_KEY] = True
    request_scroll("question-picker")
    if switch_page is not None:
        st.switch_page(switch_page)


def consume_picker_focus() -> bool:
    if not st.session_state.get(PICKER_FOCUS_KEY):
        return False
    st.session_state[PICKER_FOCUS_KEY] = False
    request_scroll("question-picker")
    return True


def _render_html_fallback(target: str, nonce: str) -> None:
    payload = json.dumps({"target": target, "nonce": nonce})
    components_v1.html(
        f"""
<!DOCTYPE html>
<html><body>
<script>
(function () {{
  const spec = {payload};
  const key = String(spec.nonce) + ":" + String(spec.target);
  const parentWin = window.parent;
  if (!parentWin || parentWin.__sage125ScrollNonce === key) {{
    return;
  }}
  parentWin.__sage125ScrollNonce = key;
  const el = parentWin.document.getElementById(spec.target);
  if (!el) {{
    return;
  }}
  const reduce = parentWin.matchMedia("(prefers-reduced-motion: reduce)").matches;
  parentWin.requestAnimationFrame(function () {{
    el.scrollIntoView({{
      behavior: reduce ? "auto" : "smooth",
      block: "start",
      inline: "nearest"
    }});
  }});
}})();
</script>
</body></html>
""",
        height=0,
        scrolling=False,
    )


def _render_ccv2(target: str, nonce: str) -> bool:
    try:
        from sage125_landing import sage125_scroll
    except Exception:
        return False
    try:
        sage125_scroll(scroll_target=target, nonce=nonce, key="sage125-scroll-trigger")
        return True
    except Exception:
        return False


def render_scroll_trigger() -> None:
    target, nonce = consume_scroll_target()
    if not target or not nonce:
        return
    if not _render_ccv2(target, nonce):
        _render_html_fallback(target, nonce)
