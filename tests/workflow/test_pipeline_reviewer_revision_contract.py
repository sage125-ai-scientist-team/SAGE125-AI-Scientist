# -*- coding: utf-8 -*-
"""Reviewer 自动修订的输入、迭代、阻断与假迭代红灯契约测试。"""

from __future__ import annotations

import copy
import hashlib
import json
from types import SimpleNamespace

from app.agents.experiment_designer import ExperimentDesignerAgent
from app.agents.hypothesis_generator import HypothesisGeneratorAgent
from app.agents.scientific_reviewer import ScientificReviewerAgent
from app.workflow.pipeline import run_pipeline_with_state
from tests.helpers_questions_fixture import write_minimal_questions_fixture


_REVIEW_FIELDS = (
    "critical_issues",
    "required_revisions",
    "reviewer_comments",
)


def _configure_offline_run(monkeypatch, tmp_path) -> str:
    """配置无需仓库外部问题目录或真实模型的最小pipeline运行。"""
    questions = write_minimal_questions_fixture(
        tmp_path / "questions_125.json",
        question_id="Q001",
    )
    monkeypatch.setenv("SAGE_QUESTIONS_PATH", str(questions))
    monkeypatch.setenv("MOCK_LLM", "true")
    return "Q001"


def _complete_input_fingerprint(value: dict) -> str:
    """按契约对完整input_data做确定性SHA-256，不使用生产端截断摘要。"""
    normalized = json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _assert_review_fields_match(actual_input: dict, expected_review: dict) -> None:
    """断言下一轮输入携带首轮完整Reviewer反馈。"""
    assert "review_result" in actual_input, (
        "第二轮输入缺少 review_result，首轮Reviewer反馈未进入下一轮"
    )
    actual_review = actual_input["review_result"]
    for field in _REVIEW_FIELDS:
        assert field in actual_review, f"第二轮 review_result 缺少真实字段 {field}"
        assert actual_review[field] == expected_review[field], (
            f"第二轮 review_result.{field} 未原样保留首轮Reviewer结果"
        )


def _run_captured_auto_revision(monkeypatch, tmp_path):
    """运行真实mock自动修订路径，并捕获三个Agent每轮的真实输入/输出。"""
    question_id = _configure_offline_run(monkeypatch, tmp_path)
    monkeypatch.setenv("MOCK_REVIEW_FAIL", "true")

    hypothesis_inputs: list[dict] = []
    experiment_inputs: list[dict] = []
    experiment_agents: list[ExperimentDesignerAgent] = []
    review_results: list[dict] = []

    original_hypothesis_run = HypothesisGeneratorAgent.run
    original_experiment_run = ExperimentDesignerAgent.run
    original_reviewer_run = ScientificReviewerAgent.run

    def capture_hypothesis(self, input_data, state, step_index=0):
        hypothesis_inputs.append(copy.deepcopy(input_data))
        return original_hypothesis_run(self, input_data, state, step_index)

    def capture_experiment(self, input_data, state, step_index=0):
        experiment_inputs.append(copy.deepcopy(input_data))
        experiment_agents.append(self)
        return original_experiment_run(self, input_data, state, step_index)

    def capture_reviewer(self, input_data, state, step_index=0):
        result = original_reviewer_run(self, input_data, state, step_index)
        review_results.append(copy.deepcopy(result))
        return result

    monkeypatch.setattr(HypothesisGeneratorAgent, "run", capture_hypothesis)
    monkeypatch.setattr(ExperimentDesignerAgent, "run", capture_experiment)
    monkeypatch.setattr(ScientificReviewerAgent, "run", capture_reviewer)

    plan, state = run_pipeline_with_state(question_id, mock_mode=True)
    return SimpleNamespace(
        plan=plan,
        state=state,
        hypothesis_inputs=hypothesis_inputs,
        experiment_inputs=experiment_inputs,
        experiment_agents=experiment_agents,
        review_results=review_results,
    )


def _review_result(
    *,
    passed: bool,
    required_revisions: list[str],
    reviewer_comments: list[str],
) -> dict:
    """构造字段完整的受控ReviewResult字典。"""
    return {
        "passed": passed,
        "reviewer_comments": list(reviewer_comments),
        "critical_issues": [],
        "required_revisions": list(required_revisions),
        "risk_level": "medium",
        "evidence_grounding_score": 0.7,
        "falsifiability_score": 0.7,
        "reproducibility_score": 0.7,
        "reference_reliability_score": 0.7,
    }


def _run_passed_but_blocking_review(monkeypatch, tmp_path):
    """让首轮Reviewer返回passed=True但仍有required revisions。"""
    question_id = _configure_offline_run(monkeypatch, tmp_path)
    monkeypatch.delenv("MOCK_REVIEW_FAIL", raising=False)

    hypothesis_inputs: list[dict] = []
    review_results: list[dict] = []
    original_hypothesis_run = HypothesisGeneratorAgent.run

    blocking_review = _review_result(
        passed=True,
        required_revisions=["必须修订"],
        reviewer_comments=["请按要求修改"],
    )
    clear_review = _review_result(
        passed=True,
        required_revisions=[],
        reviewer_comments=[],
    )

    def capture_hypothesis(self, input_data, state, step_index=0):
        hypothesis_inputs.append(copy.deepcopy(input_data))
        return original_hypothesis_run(self, input_data, state, step_index)

    def controlled_reviewer(self, input_data, state, step_index=0):
        result = blocking_review if not review_results else clear_review
        review_results.append(copy.deepcopy(result))
        return copy.deepcopy(result)

    monkeypatch.setattr(HypothesisGeneratorAgent, "run", capture_hypothesis)
    monkeypatch.setattr(ScientificReviewerAgent, "run", controlled_reviewer)

    plan, state = run_pipeline_with_state(question_id, mock_mode=True)
    return SimpleNamespace(
        plan=plan,
        state=state,
        hypothesis_inputs=hypothesis_inputs,
        review_results=review_results,
    )


def test_review_feedback_enters_second_hypothesis_input(monkeypatch, tmp_path):
    """A：第二轮HypothesisGenerator必须收到首轮完整ReviewResult。"""
    run = _run_captured_auto_revision(monkeypatch, tmp_path)

    assert len(run.hypothesis_inputs) == 2, "HypothesisGenerator未执行完整两轮"
    assert len(run.review_results) == 2, "Reviewer未执行完整两轮"
    _assert_review_fields_match(
        run.hypothesis_inputs[1],
        run.review_results[0],
    )
    assert run.hypothesis_inputs[1].get("revision_iteration") == 2, (
        "第二轮HypothesisGenerator输入缺少 revision_iteration=2"
    )


def test_review_feedback_enters_second_experiment_input(monkeypatch, tmp_path):
    """B：第二轮ExperimentDesigner输入和最终user消息都必须含Reviewer反馈。"""
    run = _run_captured_auto_revision(monkeypatch, tmp_path)

    assert len(run.experiment_inputs) == 2, "ExperimentDesigner未执行完整两轮"
    second_input = run.experiment_inputs[1]
    _assert_review_fields_match(second_input, run.review_results[0])
    assert second_input.get("revision_iteration") == 2, (
        "第二轮ExperimentDesigner输入缺少 revision_iteration=2"
    )

    messages = run.experiment_agents[1].build_messages(second_input)
    user_payload = json.loads(messages[1]["content"])
    assert "review_result" in user_payload, (
        "ExperimentDesigner.build_messages()丢弃了第二轮review_result"
    )
    for field in _REVIEW_FIELDS:
        assert user_payload["review_result"][field] == run.review_results[0][field], (
            f"ExperimentDesigner实际user消息缺少首轮Reviewer字段 {field}"
        )


def test_revision_iteration_increments_from_one_to_two(monkeypatch, tmp_path):
    """C：两个生成Agent必须分别观察到语义迭代[1, 2]。"""
    run = _run_captured_auto_revision(monkeypatch, tmp_path)

    observed = {
        "hypothesis_generator": [
            value.get("revision_iteration") for value in run.hypothesis_inputs
        ],
        "experiment_designer": [
            value.get("revision_iteration") for value in run.experiment_inputs
        ],
    }
    assert observed == {
        "hypothesis_generator": [1, 2],
        "experiment_designer": [1, 2],
    }, "revision_iteration缺失或未按1→2递增；step_index不能替代该字段"


def test_feedback_changes_second_round_input_fingerprint(monkeypatch, tmp_path):
    """D：实质Reviewer反馈必须改变HypothesisGenerator完整输入指纹。"""
    run = _run_captured_auto_revision(monkeypatch, tmp_path)

    assert len(run.hypothesis_inputs) == 2, "HypothesisGenerator未执行完整两轮"
    fingerprints = [
        _complete_input_fingerprint(value) for value in run.hypothesis_inputs
    ]
    assert fingerprints[0] != fingerprints[1], (
        "两轮HypothesisGenerator完整input_data指纹相同，属于无实质输入变化"
    )
    _assert_review_fields_match(
        run.hypothesis_inputs[1],
        run.review_results[0],
    )


def test_required_revisions_prevent_early_stop(monkeypatch, tmp_path):
    """E：passed=True但required revisions非空时仍必须进入第二轮。"""
    run = _run_passed_but_blocking_review(monkeypatch, tmp_path)

    observed_calls = {
        "hypothesis_generator": len(run.hypothesis_inputs),
        "scientific_reviewer": len(run.review_results),
    }
    assert observed_calls == {
        "hypothesis_generator": 2,
        "scientific_reviewer": 2,
    }, "required_revisions非空却在第一轮提前停止，未执行第二轮生成与评审"


def test_identical_prompt_hash_cannot_count_as_successful_revision(
    monkeypatch,
    tmp_path,
):
    """F：相同输入、历史增加、mock转通过的组合不得算成功修订。"""
    run = _run_captured_auto_revision(monkeypatch, tmp_path)

    hypothesis_events = [
        event
        for event in run.state.agent_trace
        if event.get("agent_name") == "hypothesis_generator"
    ]
    experiment_events = [
        event
        for event in run.state.agent_trace
        if event.get("agent_name") == "experiment_designer"
    ]
    assert len(hypothesis_events) == 2, "缺少两轮HypothesisGenerator trace"
    assert len(experiment_events) == 2, "缺少两轮ExperimentDesigner trace"
    assert len(run.review_results) == 2, "缺少两轮Reviewer结果"

    same_substantive_inputs = (
        run.hypothesis_inputs[0] == run.hypothesis_inputs[1]
        and run.experiment_inputs[0] == run.experiment_inputs[1]
    )
    same_prompt_hashes = (
        hypothesis_events[0]["prompt_hash"] == hypothesis_events[1]["prompt_hash"]
        and experiment_events[0]["prompt_hash"] == experiment_events[1]["prompt_hash"]
    )
    history_added = bool(run.state.revision_history)
    reviewer_switched_to_pass = (
        run.review_results[0]["passed"] is False
        and run.review_results[1]["passed"] is True
    )

    assert not (
        same_substantive_inputs
        and same_prompt_hashes
        and history_added
        and reviewer_switched_to_pass
    ), (
        "两轮实质输入和prompt_hash相同，但revision_history增加且mock Reviewer转为通过；"
        "该组合是可识别的假迭代，不能算成功修订"
    )


def test_passed_review_with_blocking_revisions_is_not_effectively_passing(
    monkeypatch,
    tmp_path,
):
    """防御性一致性：终态不能保留passed=True与未解决阻断修订。"""
    run = _run_passed_but_blocking_review(monkeypatch, tmp_path)

    assert not run.state.review_result.get("required_revisions"), (
        "pipeline终态仍保留required_revisions，却把passed=True当作有效通过"
    )
