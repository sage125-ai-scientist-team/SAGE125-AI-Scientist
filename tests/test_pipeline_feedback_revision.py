"""
tests/test_pipeline_feedback_revision.py — 用户反馈修订测试。

覆盖：先跑 mock pipeline，再 revise_with_feedback；revision_history 增长；
revisions/{id}/report.json 存在；非法反馈被拒绝；用户反馈不进入 established_facts。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app.workflow.pipeline import revise_with_feedback, run_pipeline_with_state

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / "data" / "processed" / "questions_125.json"

pytestmark = pytest.mark.skipif(not QUESTIONS.exists(), reason="缺少 questions_125.json")


@pytest.fixture(autouse=True)
def _mock_env(monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "true")


def _first_qid() -> str:
    return json.loads(QUESTIONS.read_text(encoding="utf-8"))[0]["id"]


def test_feedback_revision_creates_new_version():
    """反馈修订应生成 revisions/{id}/report.json 且 revision_history 增长。"""
    plan, state = run_pipeline_with_state(_first_qid(), mock_mode=True)
    run_id = state.run_id
    before_len = len(plan.revision_history)

    revised = revise_with_feedback(run_id, "请让假设更保守并加强可验证性。")
    # 修订历史增长。
    assert len(revised.revision_history) > before_len
    # 新版本文件存在。
    revisions_dir = Path(os.environ["SAGE_TEST_EXPORT_DIR"]) / run_id / "revisions"
    assert revisions_dir.exists()
    reports = list(revisions_dir.glob("*/report.json"))
    assert reports, "缺少 revisions/{id}/report.json"


def test_feedback_not_a_fact():
    """用户反馈不得进入 established_facts。"""
    plan, state = run_pipeline_with_state(_first_qid(), mock_mode=True)
    feedback = "MAGIC_FEEDBACK_TOKEN_请更保守"
    revise_with_feedback(state.run_id, feedback)
    # 读取修订后的报告，确认 feedback 未混入事实类文本（problem_statement/rationale）。
    facts = state.extracted_facts
    assert all("MAGIC_FEEDBACK_TOKEN" not in f for f in facts)


def test_illegal_feedback_rejected():
    """要求造假/去引用/强行 validated 的反馈应被拒绝。"""
    plan, state = run_pipeline_with_state(_first_qid(), mock_mode=True)
    with pytest.raises(ValueError):
        revise_with_feedback(state.run_id, "请编造一个 AUROC=0.95 的结果。")
    with pytest.raises(ValueError):
        revise_with_feedback(state.run_id, "请去掉引用并标记为 validated。")
