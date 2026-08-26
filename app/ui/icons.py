# -*- coding: utf-8 -*-
"""少量 Lucide 风格线性 SVG，按需内联，不打包图标字体。"""

from __future__ import annotations

from app.ui.components import esc

_LUCIDE = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
    'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" '
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{path}</svg>'
)

PATHS = {
    "file-search": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>'
    '<path d="M14 2v6h6"/><circle cx="11.5" cy="14.5" r="2.5"/><path d="m13.3 16.3 1.7 1.7"/>',
    "flask-conical": '<path d="M10 2v7.31"/><path d="M14 9.3V2"/>'
    '<path d="M8.5 2h7"/><path d="M6.5 22h11l-3.2-8.4a5 5 0 0 0-4.6 0L6.5 22z"/>',
    "users": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/>'
    '<circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/>'
    '<path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    "shield-check": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>'
    '<path d="m9 12 2 2 4-4"/>',
    "circle-dot": '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3"/>',
    "library": '<path d="m16 6 4 14"/><path d="M12 6v14"/><path d="M8 8v12"/>'
    '<path d="M4 4v16"/>',
    "git-branch": '<circle cx="6" cy="6" r="3"/><path d="M6 9v12"/>'
    '<circle cx="18" cy="18" r="3"/><path d="M18 9a9 9 0 0 0-9 9"/>',
    "clipboard-list": '<rect width="8" height="4" x="8" y="2" rx="1"/>'
    '<path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>'
    '<path d="M9 14h6"/><path d="M9 18h6"/><path d="M9 10h.01"/>',
    "play": '<polygon points="6 3 20 12 6 21 6 3"/>',
    "history": '<path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 3v6h6"/><path d="M12 7v5l3 3"/>',
    "download": '<path d="M12 3v12"/><path d="m8 11 4 4 4-4"/><path d="M4 21h16"/>',
    "database": '<ellipse cx="12" cy="5" rx="9" ry="3"/>'
    '<path d="M3 5v14c0 1.7 4 3 9 3s9-1.3 9-3V5"/><path d="M3 12c0 1.7 4 3 9 3s9-1.3 9-3"/>',
    "settings": '<path d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z"/>'
    '<path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9c.3.7 1 1.2 1.8 1.3H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
    "layout": '<rect width="7" height="9" x="3" y="3" rx="1"/>'
    '<rect width="7" height="5" x="14" y="3" rx="1"/>'
    '<rect width="7" height="9" x="14" y="12" rx="1"/>'
    '<rect width="7" height="5" x="3" y="16" rx="1"/>',
}


def lucide(name: str, size: int = 18) -> str:
    """返回已转义尺寸的 Lucide 风格 SVG。未知名称回退为点。"""
    path = PATHS.get(name, PATHS["circle-dot"])
    return _LUCIDE.format(size=int(size), path=path)


def icon_label(name: str, text: str, size: int = 18) -> str:
    """图标 + 文本，供安全 HTML 使用。"""
    return f'<span class="sage-icon-label">{lucide(name, size)}<span>{esc(text)}</span></span>'
