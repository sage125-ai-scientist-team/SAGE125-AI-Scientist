"""
app.ui.key_factory —— Streamlit widget key 统一生成器（修复 DuplicateElementKey）。

问题背景：
    多个 download_button/button 使用形如 f"dl_{i}" 的弱 key，跨区域/跨 run 复用时
    发生 StreamlitDuplicateElementKey。本模块提供 make_widget_key，拼接
    namespace/run_id/section/filename/index 并只保留安全字符，保证全局唯一，
    同时维护 st.session_state["_used_widget_keys"] 以便重复检测。

约束：
    - 所有交互组件（download_button/button/selectbox/multiselect/slider/checkbox/
      radio/text_input/file_uploader 等）都应使用 make_widget_key 生成 key；
    - 禁止再出现 key="dl_0" / key=f"dl_{i}" 这类弱 key。
"""

from __future__ import annotations

import re
from typing import Any

# 允许的安全字符：字母数字、下划线、连字符、点。
_SAFE_CHARS = re.compile(r"[^0-9A-Za-z_.-]+")
# 单个 key 的最大长度（避免超长 key）。
_MAX_LEN = 120


def _sanitize(part: Any) -> str:
    """将单个片段规范化为安全字符串。"""
    text = str("" if part is None else part).strip()
    # 空白替换为下划线，其余非安全字符替换为连字符。
    text = text.replace(" ", "_")
    text = _SAFE_CHARS.sub("-", text)
    return text


def make_widget_key(*parts: Any) -> str:
    """
    由多个片段拼接生成全局唯一、字符安全的 widget key。

    参数：
        *parts: 组成 key 的片段（如 namespace、run_id、section、filename、index）。

    返回：
        规范化后的 key 字符串（形如 "download__run123__report.json__0"）。
    """
    pieces = [_sanitize(p) for p in parts if p is not None and str(p) != ""]
    key = "__".join(pieces) if pieces else "widget"
    # 控制长度：过长则保留头部 + 末尾 hash 片段，保证仍唯一。
    if len(key) > _MAX_LEN:
        import hashlib

        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:8]
        key = key[: _MAX_LEN - 9] + "_" + digest
    return key


def register_key(key: str) -> bool:
    """
    在 session_state 中登记一个 key，检测是否重复（用于测试/调试）。

    参数：
        key: 待登记的 widget key。

    返回：
        True 表示首次登记（唯一）；False 表示已存在（重复）。
    """
    try:
        import streamlit as st
    except Exception:  # noqa: BLE001
        # 非 streamlit 上下文（如单元测试）直接视为唯一。
        return True
    used = st.session_state.setdefault("_used_widget_keys", set())
    if key in used:
        return False
    used.add(key)
    return True


def reset_registry() -> None:
    """清空 key 登记表（每次 rerun 顶部调用，避免误报重复）。"""
    try:
        import streamlit as st
    except Exception:  # noqa: BLE001
        return
    st.session_state["_used_widget_keys"] = set()
