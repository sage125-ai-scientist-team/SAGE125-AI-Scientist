"""
tests/test_batch_125_mock.py — 125 批量 mock 测试。

覆盖：--mock --max-questions 3 生成 batch_outputs_125.jsonl；每条 results_pending=true；
validation_status 不为 validated；mock 证据标记存在。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / "data" / "processed" / "questions_125.json"

import pytest

pytestmark = pytest.mark.skipif(not QUESTIONS.exists(), reason="缺少 questions_125.json")


def test_batch_mock(tmp_path):
    """mock 批处理 3 题应生成 jsonl，且 Results 全 pending、非 validated。"""
    out_dir = tmp_path / "batch"
    env = dict(os.environ)
    env["MOCK_LLM"] = "true"
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_batch_125.py"), "--mock",
         "--max-questions", "3", "--output-dir", str(out_dir)],
        cwd=str(ROOT), capture_output=True, text=True, timeout=300, env=env,
    )
    assert proc.returncode == 0, proc.stderr
    jsonl = out_dir / "batch_outputs_125.jsonl"
    assert jsonl.exists()
    rows = [json.loads(line) for line in jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 3
    for r in rows:
        assert r["results_pending"] is True
        assert r["validation_status"] != "validated"

    # 校验某题产物含 mock 证据标记。
    first = rows[0]["question_id"]
    ev_path = out_dir / first / "evidence_cards.json"
    assert ev_path.exists()
    assert "mock_for_testing" in ev_path.read_text(encoding="utf-8")
