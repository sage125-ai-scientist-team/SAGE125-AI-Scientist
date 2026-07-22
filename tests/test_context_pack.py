"""
tests/test_context_pack.py — 上下文包测试。

覆盖：context_pack.json 存在且包含 selected_question / evidence_pack /
candidate_hypotheses / quality_gates；不含 .env、不含完整 API Key。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app.workflow.pipeline import run_pipeline_with_state

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / "data" / "processed" / "questions_125.json"

pytestmark = pytest.mark.skipif(not QUESTIONS.exists(), reason="缺少 questions_125.json")


def _first_qid() -> str:
    return json.loads(QUESTIONS.read_text(encoding="utf-8"))[0]["id"]


def test_context_pack(monkeypatch):
    """context_pack 应包含关键字段且不泄露敏感信息。"""
    monkeypatch.setenv("MOCK_LLM", "true")
    plan, state = run_pipeline_with_state(_first_qid(), mock_mode=True)

    path = Path(os.environ["SAGE_TEST_EXPORT_DIR"]) / state.run_id / "context_pack.json"
    assert path.exists()
    pack = json.loads(path.read_text(encoding="utf-8"))

    # 关键字段存在。
    assert "selected_question" in pack
    assert "evidence_pack" in pack
    assert "candidate_hypotheses" in pack
    assert "quality_gates" in pack

    # 不含 .env 与完整 Key。
    blob = json.dumps(pack, ensure_ascii=False)
    assert "DASHSCOPE_API_KEY=" not in blob
    assert "sk-" not in blob or "sk-****" in blob
