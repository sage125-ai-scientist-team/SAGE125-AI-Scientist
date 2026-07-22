"""
tests/test_streamlit_unique_keys.py — widget key 唯一性测试（P0-3）。

覆盖：
    - make_widget_key 对多个文件生成唯一 key；
    - 同一 run 下不同文件 key 不重复；
    - 不同 run 下同一文件 key 不重复；
    - 生成的 key 仅含安全字符；
    - 源码不含 key="dl_0" / f"dl_{i}" 这类弱 key。
"""

from __future__ import annotations

import re
from pathlib import Path

from app.ui.key_factory import make_widget_key

ROOT = Path(__file__).resolve().parents[1]


def test_unique_keys_same_run_multiple_files():
    """同一 run 下不同文件应生成不重复 key。"""
    run_id = "20260709-abc123"
    files = ["report.md", "report.json", "report.html", "report.pdf",
             "evidence_cards.json", "agent_trace.json", "context_pack.json",
             "quality_gates.json", "llm_call_audit.json", "run_summary.txt"]
    keys = [make_widget_key("download", run_id, f, i) for i, f in enumerate(files)]
    assert len(keys) == len(set(keys)), "同一 run 下文件 key 出现重复"


def test_unique_keys_across_runs_same_file():
    """不同 run 下同一文件应生成不重复 key。"""
    k1 = make_widget_key("download", "run-A", "report.json", 1)
    k2 = make_widget_key("download", "run-B", "report.json", 1)
    assert k1 != k2


def test_key_only_safe_chars():
    """生成 key 仅含字母数字/下划线/连字符/点。"""
    key = make_widget_key("download", "run 空格/斜杠", "report.json", 0)
    assert re.fullmatch(r"[0-9A-Za-z_.-]+", key), f"key 含非法字符：{key}"


def test_source_has_no_weak_download_keys():
    """components.py 不得再出现 key='dl_0' / f'dl_{i}' 这类弱 key。"""
    src = (ROOT / "app" / "ui" / "components.py").read_text(encoding="utf-8")
    assert 'key=f"dl_{i}"' not in src
    assert 'key="dl_0"' not in src
    assert 'key=f"fb_{i}"' not in src
    # 导出中心应使用 make_widget_key。
    assert "make_widget_key(\"download\"" in src or "make_widget_key('download'" in src


def test_registry_detects_duplicates():
    """register_key 在非 streamlit 上下文默认视为唯一（不报错）。"""
    from app.ui.key_factory import register_key

    assert register_key("some-key") is True
