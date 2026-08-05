"""
Q028 回归场景 — T01 Wave B（08/02）。

在契约/检查器层复现手册要求的失败与修复后行为：
1. 不得出现虚构 ``booklet_excerpt_Q028``；
2. booklet 不得支撑 established facts；
3. 单一癌种证据不得无条件外推到所有癌症。

不修改 ``pipeline.py``；运行时接入由 T02 完成。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.contracts.evidence import EvidenceCardContract
from app.evidence.support_checker import (
    ClaimText,
    SupportCheckResult,
    SupportErrorCode,
    check_claim_evidence_support,
)


@dataclass
class Q028ScenarioResult:
    """
    单个 Q028 回归场景结果。

    属性：
        scenario_id: 场景编号。
        title: 场景标题。
        before_note: 修复前行为说明。
        after: 当前检查器结果。
        expected_codes: 期望出现的错误码。
        passed: 是否达到期望。
    """

    scenario_id: str
    title: str
    before_note: str
    after: SupportCheckResult
    expected_codes: list[str]
    passed: bool


@dataclass
class Q028RegressionReport:
    """
    Q028 回归汇总。

    属性：
        scenarios: 场景结果列表。
        all_passed: 是否全部通过。
    """

    scenarios: list[Q028ScenarioResult] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        """全部场景是否通过。"""
        return bool(self.scenarios) and all(item.passed for item in self.scenarios)

    def to_dict(self) -> dict[str, Any]:
        """序列化为可写入报告的 dict。"""
        return {
            "all_passed": self.all_passed,
            "scenarios": [
                {
                    "scenario_id": s.scenario_id,
                    "title": s.title,
                    "before_note": s.before_note,
                    "expected_codes": s.expected_codes,
                    "actual_codes": s.after.error_codes,
                    "blocked": s.after.blocked,
                    "degraded_claim_ids": s.after.degraded_claim_ids,
                    "allowed_link_count": len(s.after.allowed_links),
                    "passed": s.passed,
                }
                for s in self.scenarios
            ],
        }


def _lung_adeno_card() -> EvidenceCardContract:
    """构造肺腺癌论文证据卡（合法非 booklet）。"""
    return EvidenceCardContract(
        evidence_id="EV-Q028-LUNG",
        source_id="10.1234/q028-lung",
        source_type="paper",
        title="EGFR response in lung adenocarcinoma",
        quoted_text=(
            "EGFR inhibition improves response in lung adenocarcinoma samples "
            "under the reported cohort."
        ),
        locator={"page": 4, "section": "Results"},
        authors=["Lee"],
        year=2023,
        doi="10.1234/q028-lung",
        content_hash="sha256:q028-lung",
        domain="oncology",
        verification_status="pending",
    )


def _booklet_card() -> EvidenceCardContract:
    """构造问题册来源证据卡。"""
    return EvidenceCardContract(
        evidence_id="EV-Q028-BOOKLET",
        source_id="booklet-Q028",
        source_type="question_booklet",
        title="Q028 question context",
        quoted_text="Booklet question text about cancer broadly for students.",
        locator={"source": "booklet", "question_id": "Q028"},
        content_hash="sha256:q028-booklet",
        domain="oncology",
        verification_status="pending",
    )


def run_q028_regression() -> Q028RegressionReport:
    """
    运行 Q028 契约层回归场景集合。

    返回：
        Q028RegressionReport。
    """
    report = Q028RegressionReport()
    lung = _lung_adeno_card()
    booklet = _booklet_card()

    # S1: 虚构 booklet_excerpt_Q028
    s1 = check_claim_evidence_support(
        [
            ClaimText(
                claim_id="Q028-C-FAKE",
                text="All cancers respond to EGFR inhibition",
                evidence_ids=["booklet_excerpt_Q028"],
                domain="oncology",
            )
        ],
        [lung],
    )
    report.scenarios.append(
        Q028ScenarioResult(
            scenario_id="S1",
            title="Fabricated booklet_excerpt_Q028 must be blocked",
            before_note=(
                "Baseline risk: agents could invent booklet_excerpt_Q028 and treat "
                "it as a real EvidenceCard id."
            ),
            after=s1,
            expected_codes=[SupportErrorCode.FAKE_BOOKLET_EVIDENCE_ID.value],
            passed=(
                s1.blocked
                and SupportErrorCode.FAKE_BOOKLET_EVIDENCE_ID.value in s1.error_codes
                and len(s1.allowed_links) == 0
            ),
        )
    )

    # S2: booklet 支撑事实
    s2 = check_claim_evidence_support(
        [
            ClaimText(
                claim_id="Q028-C-BOOK",
                text="Booklet question text about cancer broadly for students.",
                evidence_ids=["EV-Q028-BOOKLET"],
                domain="oncology",
            )
        ],
        [booklet],
    )
    report.scenarios.append(
        Q028ScenarioResult(
            scenario_id="S2",
            title="Booklet excerpt cannot support established facts",
            before_note=(
                "Baseline risk: booklet_excerpt used as scientific evidence support."
            ),
            after=s2,
            expected_codes=[SupportErrorCode.BOOKLET_EXCLUDED.value],
            passed=(
                s2.blocked
                and SupportErrorCode.BOOKLET_EXCLUDED.value in s2.error_codes
                and len(s2.allowed_links) == 0
            ),
        )
    )

    # S3: 肺腺癌 → 所有癌症
    s3 = check_claim_evidence_support(
        [
            ClaimText(
                claim_id="Q028-C-OVER",
                text="EGFR inhibition improves response in all cancers",
                evidence_ids=["EV-Q028-LUNG"],
                domain="oncology",
            )
        ],
        [lung],
    )
    report.scenarios.append(
        Q028ScenarioResult(
            scenario_id="S3",
            title="Single-cancer evidence cannot support all-cancer claim",
            before_note=(
                "Baseline risk: lung adenocarcinoma quote used to justify "
                "unconditional claims about all cancers."
            ),
            after=s3,
            expected_codes=[SupportErrorCode.OVERGENERALIZATION.value],
            passed=(
                (not s3.blocked)
                and SupportErrorCode.OVERGENERALIZATION.value in s3.error_codes
                and "Q028-C-OVER" in s3.degraded_claim_ids
                and len(s3.allowed_links) == 0
            ),
        )
    )

    # S4: 合法同范围声明应 allow
    s4 = check_claim_evidence_support(
        [
            ClaimText(
                claim_id="Q028-C-OK",
                text="EGFR inhibition improves response in lung adenocarcinoma",
                evidence_ids=["EV-Q028-LUNG"],
                domain="oncology",
            )
        ],
        [lung],
    )
    report.scenarios.append(
        Q028ScenarioResult(
            scenario_id="S4",
            title="In-scope lung adenocarcinoma claim remains allow",
            before_note="Control: matching claim/evidence should still pass.",
            after=s4,
            expected_codes=[],
            passed=(
                (not s4.blocked)
                and s4.degraded_claim_ids == []
                and len(s4.allowed_links) == 1
            ),
        )
    )

    return report
