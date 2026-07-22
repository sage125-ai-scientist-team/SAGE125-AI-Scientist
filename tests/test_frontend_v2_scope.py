"""
tests/test_frontend_v2_scope.py — 前端 V2 范围校验。

覆盖：前端源码包含 V2 区域名称，且不含参赛提交材料相关措辞。
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _src() -> str:
    """拼接前端关键源码文本。"""
    parts = []
    for name in ("streamlit_app.py", "components.py"):
        p = ROOT / "app" / "ui" / name
        parts.append(p.read_text(encoding="utf-8") if p.exists() else "")
    return "\n".join(parts)


def test_frontend_contains_v2_regions():
    """前端应包含 V2 区域名称。"""
    src = _src()
    for token in ("First Run Wizard", "Agent Observatory", "Evidence Wall",
                  "ResearchPlan Studio", "ResearchPlan Export Center"):
        assert token in src, f"前端缺少区域：{token}"


def test_frontend_no_submission_tokens():
    """前端不含参赛提交材料相关措辞。"""
    src = _src()
    for token in ("Submission Export Center", "technical_solution.pdf", "demo_script_10min", "submission_bundle"):
        assert token not in src, f"前端仍含禁用措辞：{token}"
