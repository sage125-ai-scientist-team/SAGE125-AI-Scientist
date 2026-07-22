"""
tests/test_user_guide_scope.py — USER_GUIDE 范围校验。

覆盖：不把最终 PDF/PPT/视频当作项目自动输出；包含 mock/real/doctor 路径与前端使用说明。
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "docs" / "USER_GUIDE.md"


def test_user_guide_exists():
    """USER_GUIDE.md 应存在。"""
    assert GUIDE.exists()


def test_user_guide_scope_disclaimer():
    """明确说明不自动生成参赛材料。"""
    text = GUIDE.read_text(encoding="utf-8")
    assert "不自动生成" in text
    assert "人工整理" in text


def test_user_guide_paths_present():
    """包含 mock / real / doctor / 前端使用路径。"""
    text = GUIDE.read_text(encoding="utf-8")
    assert "run_demo.py" in text            # mock/real 路径
    assert "setup_env.py" in text           # real 前置
    assert "--real" in text                 # real 模式
    assert "doctor.py" in text              # 诊断
    assert "streamlit run app/ui/streamlit_app.py" in text  # 前端使用
