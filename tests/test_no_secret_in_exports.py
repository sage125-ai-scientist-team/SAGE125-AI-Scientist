"""
tests/test_no_secret_in_exports.py — 导出物无敏感信息扫描。

覆盖：全部 exports 运行产物不含 sk- 长串、不含真实
DASHSCOPE_API_KEY 赋值、不含 .env 内容、不含完整 Windows 用户路径。
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN_DIRS = [ROOT / "exports"]

_SECRET = re.compile(r"sk-[A-Za-z0-9]{16,}")
_REAL_KEY = re.compile(r"DASHSCOPE_API_KEY\s*=\s*sk-[A-Za-z0-9]{8,}")
_PRIVATE_PATH = re.compile(r"[Cc]:\\Users\\[^\\\s\"']+")


def _iter_files():
    """产出待扫描的导出文件。"""
    for d in SCAN_DIRS:
        if not d.exists():
            continue
        for p in d.rglob("*"):
            if p.is_file() and p.suffix in (".json", ".md", ".csv", ".jsonl", ".html", ".txt"):
                yield p


def test_no_secret_in_exports():
    """导出物不得包含密钥/真实 Key 赋值/私有路径。"""
    offenders = []
    for p in _iter_files():
        text = p.read_text(encoding="utf-8", errors="ignore")
        if _SECRET.search(text):
            offenders.append(f"{p.name}: secret")
        if _REAL_KEY.search(text):
            offenders.append(f"{p.name}: real key assign")
        if _PRIVATE_PATH.search(text):
            offenders.append(f"{p.name}: private path")
    assert not offenders, f"导出物含敏感信息：{offenders}"
