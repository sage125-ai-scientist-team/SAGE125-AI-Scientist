"""Single source of truth for Q028's pre-registered experimental protocol.

Both ``app.workflow.mock_outputs`` (Mock 演示) and
``app.agents.experiment_designer`` (真实 LLM 模式) source the
"Experiments"/"Datasets"/"Methods"/"Technical Details" fields shown in the
ResearchPlan Studio for Q028 from this module. That way the on-screen plan
can never drift from the fixed protocol that
``app.execution.wdbc_baseline`` / ``app.execution.q028_demo_run`` actually
execute — independent of whether the plan text itself was produced by Mock
or by a real LLM call.

This mirrors how pre-registered studies work in real science: once a
protocol is frozen (see ``experiments/flagship/selection_manifest.json``),
no downstream narration step — generative or templated — is allowed to
silently redescribe a different method or metric. If the frozen protocol
ever needs to change, it must change here first, and both consumers pick up
the update automatically.
"""

from __future__ import annotations

#: The only question_id this module governs. Every consumer must gate on
#: this exact id rather than keyword-matching on question text.
QUESTION_ID = "Q028"


def experiment_design_fields() -> dict:
    """Return the frozen WDBC Round 1/2 protocol as ExperimentDesignResult fields.

    返回：
        含 ``technical_details``/``datasets``/``methods``/``experiments`` 的
        dict，描述与真实代码（app.execution.wdbc_baseline）严格一致的协议：
        标准化逻辑回归、balanced_accuracy 与 malignant_recall、分层留出验证。
    """
    return {
        "technical_details": (
            "固定随机种子做分层留出切分；对 30 项特征做标准化；使用全批量梯度下降训练标准化"
            "逻辑回归；在留出测试集上计算 balanced accuracy 与 malignant recall；若召回率低于"
            "目标，Round 2 复测更低的决策阈值。"
        ),
        "datasets": {
            "source": "UCI WDBC Diagnostic 数据集（1995-10-31 版本，569 条记录，30 项特征，已固定 SHA-256 pin）",
            "target": "诊断标签：良性 (B) / 恶性 (M)，来自数据集原始标注",
        },
        "methods": "特征标准化 + 逻辑回归（全批量梯度下降）+ 分层留出验证 + 阈值敏感性分析。",
        "experiments": {
            "baselines": ["标准化逻辑回归（Round 1 基线）"],
            "metrics": ["balanced_accuracy", "malignant_recall"],
            "ablation": ["Round 2：调整决策阈值以提升 malignant_recall"],
            "validation_protocol": "分层留出验证（stratified holdout）+ 固定随机种子，可通过脚本一键复现。",
        },
    }


def is_flagship_question(question_item: dict | None) -> bool:
    """question_item 是否精确对应 Q028（按 id，不按关键词/题文匹配）。"""
    if not question_item:
        return False
    return str(question_item.get("id") or "").strip().upper() == QUESTION_ID
