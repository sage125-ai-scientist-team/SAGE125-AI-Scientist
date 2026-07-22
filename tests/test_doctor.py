"""
tests/test_doctor.py — doctor 诊断脚本测试。

覆盖：doctor --mock 可运行；输出不含 API Key；含 questions 修复命令；
含“无参赛材料残留”检查项；生成 doctor_report.json。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "exports" / "doctor" / "doctor_report.json"
_SECRET = re.compile(r"sk-[A-Za-z0-9]{16,}")


def test_doctor_mock_runs():
    """doctor --mock 运行成功并产出报告，输出不含 Key。"""
    env = dict(os.environ)
    env["MOCK_LLM"] = "true"
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "doctor.py"), "--mock", "--json"],
        cwd=str(ROOT), capture_output=True, text=True, timeout=120, env=env,
    )
    # 返回码 0（warning）或 1（error 环境），均不应崩溃。
    assert proc.returncode in (0, 1)
    # 输出无明文 Key。
    assert not _SECRET.search(proc.stdout)
    # 报告存在。
    assert REPORT.exists()
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    labels = [c["label"] for c in report["checks"]]
    # 含 questions 检查（带修复命令）。
    q_checks = [c for c in report["checks"] if "questions_125.json" in c["label"]]
    assert q_checks and "extract_125_questions" in (q_checks[0].get("fix") or "")
    # 含参赛材料残留检查。
    assert any("no submission" in lbl for lbl in labels)
