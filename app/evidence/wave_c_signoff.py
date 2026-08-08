"""
T01 Wave C（08/08）关键事实 locator 机器核验。

生成人工签字表所需的可复现检查结果；**不**伪造人工签字。
人工签字栏保持 pending，直至负责人书面确认。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional, Sequence

from app.evidence.q028_regression import run_q028_regression

DEFAULT_GOLD_PATH = Path("docs/modules/T01/evidence_gold_set.json")
# 固定种子：保证「3 个随机题」在同一 gold 上可复现。
RANDOM_SEED = "T01-WAVE-C-SIGNOFF-2026-08-08"
FLAGSHIP_CLAIM_ID = "CLAIM-013"


@dataclass(frozen=True)
class FactCheckRow:
    """
    单条关键事实核验行。

    属性：
        case_id: 案例标识。
        claim_id: 声明 ID。
        evidence_id: 证据 ID。
        has_locator: locator 是否非空。
        locator: 定位信息。
        quote_nonempty: 原文是否非空。
        machine_ok: 机器核验是否通过。
        human_signoff: 人工签字状态（默认 pending）。
        notes: 说明。
    """

    case_id: str
    claim_id: str
    evidence_id: str
    has_locator: bool
    locator: dict[str, Any]
    quote_nonempty: bool
    machine_ok: bool
    human_signoff: str = "pending"
    notes: str = ""


@dataclass
class WaveCSignoffReport:
    """
    Wave C 签字前机器核验报告。

    属性：
        git_commit_placeholder: 填写时的 HEAD（由调用方注入）。
        q028_all_passed: Q028 回归是否全过。
        rows: 核验行。
        locator_coverage: 有 locator 的行占比 0–1。
        machine_all_ok: 全部机器行是否通过。
        human_signoff_complete: 人工是否已全部签字（默认 False）。
        ready_blocked_reason: 阻断 Ready 的原因。
    """

    git_commit_placeholder: str
    q028_all_passed: bool
    rows: list[FactCheckRow] = field(default_factory=list)
    locator_coverage: float = 0.0
    machine_all_ok: bool = False
    human_signoff_complete: bool = False
    ready_blocked_reason: str = (
        "T09 revalidation pending and/or human signoff incomplete; keep Draft"
    )

    def to_dict(self) -> dict[str, Any]:
        """
        序列化为 JSON 友好 dict。

        返回：
            可 dumps 的字典。
        """
        return {
            "git_commit_placeholder": self.git_commit_placeholder,
            "q028_all_passed": self.q028_all_passed,
            "rows": [asdict(row) for row in self.rows],
            "locator_coverage": self.locator_coverage,
            "machine_all_ok": self.machine_all_ok,
            "human_signoff_complete": self.human_signoff_complete,
            "ready_blocked_reason": self.ready_blocked_reason,
            "pairing_boundary": {
                "PAIRING_STRUCTURE": "STRUCTURE_OK",
                "ACTUAL_RELEVANCE_GOLD": "NOT_READY",
                "FORMAL_RETRIEVAL_METRICS_AUTHORIZED": False,
            },
        }


def _load_pairs(gold_path: Path) -> list[dict[str, Any]]:
    """
    加载 Wave B gold pairs。

    参数：
        gold_path: JSON 路径。

    返回：
        pair dict 列表。
    """
    payload = json.loads(gold_path.read_text(encoding="utf-8"))
    pairs = payload.get("pairs") or []
    if not isinstance(pairs, list):
        raise ValueError("evidence_gold_set.pairs must be a list")
    return pairs


def _stable_pick_claim_ids(
    pairs: Sequence[dict[str, Any]],
    *,
    count: int,
    seed: str,
    exclude: Sequence[str],
) -> list[str]:
    """
    用种子做稳定伪随机选取 claim_id。

    参数：
        pairs: gold pairs。
        count: 选取数量。
        seed: 稳定种子。
        exclude: 排除的 claim_id。

    返回：
        选中的 claim_id 列表。
    """
    exclude_set = set(exclude)
    candidates = sorted(
        {
            str(pair.get("claim_id", ""))
            for pair in pairs
            if pair.get("claim_id") and pair.get("claim_id") not in exclude_set
        }
    )
    ranked = sorted(
        candidates,
        key=lambda cid: hashlib.sha256(f"{seed}:{cid}".encode("utf-8")).hexdigest(),
    )
    return ranked[:count]


def _row_from_pair(case_id: str, pair: dict[str, Any]) -> FactCheckRow:
    """
    从 gold pair 构造核验行。

    参数：
        case_id: 案例标签。
        pair: gold pair。

    返回：
        FactCheckRow。
    """
    locator = pair.get("locator") or {}
    if not isinstance(locator, dict):
        locator = {}
    quote = str(pair.get("quote") or "").strip()
    has_locator = bool(locator)
    quote_nonempty = bool(quote)
    machine_ok = has_locator and quote_nonempty
    notes = []
    if not has_locator:
        notes.append("missing_locator")
    if not quote_nonempty:
        notes.append("empty_quote")
    return FactCheckRow(
        case_id=case_id,
        claim_id=str(pair.get("claim_id", "")),
        evidence_id=str(pair.get("evidence_id", "")),
        has_locator=has_locator,
        locator=dict(locator),
        quote_nonempty=quote_nonempty,
        machine_ok=machine_ok,
        human_signoff="pending",
        notes=";".join(notes),
    )


def build_wave_c_signoff_report(
    *,
    gold_path: Path = DEFAULT_GOLD_PATH,
    git_commit: str = "HEAD",
    random_count: int = 3,
    flagship_claim_id: str = FLAGSHIP_CLAIM_ID,
) -> WaveCSignoffReport:
    """
    构建 08/08 签字表机器核验报告。

    覆盖：Q028 回归、旗舰 claim、3 个稳定伪随机题。

    参数：
        gold_path: gold JSON。
        git_commit: 当前 HEAD。
        random_count: 随机题数量。
        flagship_claim_id: 旗舰 claim。

    返回：
        WaveCSignoffReport（human_signoff 仍为 pending）。
    """
    q028 = run_q028_regression()
    pairs = _load_pairs(gold_path)
    by_claim = {str(pair.get("claim_id")): pair for pair in pairs}
    rows: list[FactCheckRow] = []

    # Q028：用回归场景作为关键事实门禁行（locator 由场景卡保证）。
    rows.append(
        FactCheckRow(
            case_id="Q028-regression",
            claim_id="Q028",
            evidence_id="(scenario-suite)",
            has_locator=True,
            locator={"source": "app.evidence.q028_regression"},
            quote_nonempty=True,
            machine_ok=q028.all_passed,
            human_signoff="pending",
            notes="contract-layer regression; not live pipeline trace",
        )
    )

    flagship = by_claim.get(flagship_claim_id)
    if flagship is None:
        # 回退到第一对多域样本。
        flagship = next(
            (
                pair
                for pair in pairs
                if str(pair.get("claim_id", "")).startswith("CLAIM-")
            ),
            pairs[0] if pairs else None,
        )
    if flagship is not None:
        rows.append(_row_from_pair("flagship", flagship))

    picked = _stable_pick_claim_ids(
        pairs,
        count=random_count,
        seed=RANDOM_SEED,
        exclude=[flagship_claim_id, str(flagship.get("claim_id")) if flagship else ""],
    )
    for index, claim_id in enumerate(picked, start=1):
        pair = by_claim[claim_id]
        rows.append(_row_from_pair(f"random-{index}", pair))

    ok_rows = [row for row in rows if row.machine_ok]
    coverage = (len(ok_rows) / len(rows)) if rows else 0.0
    machine_all_ok = bool(rows) and all(row.machine_ok for row in rows) and q028.all_passed
    return WaveCSignoffReport(
        git_commit_placeholder=git_commit,
        q028_all_passed=q028.all_passed,
        rows=rows,
        locator_coverage=coverage,
        machine_all_ok=machine_all_ok,
        human_signoff_complete=False,
        ready_blocked_reason=(
            "Keep Draft until T09 revalidation PASS and human signoff completed"
        ),
    )


def render_signoff_markdown(report: WaveCSignoffReport) -> str:
    """
    将报告渲染为签字表 Markdown。

    参数：
        report: WaveCSignoffReport。

    返回：
        Markdown 文本。
    """
    lines = [
        "# T01 Wave C — 2026-08-08 人工核验签字表（草稿）",
        "",
        f"**Checked HEAD (fill/push):** `{report.git_commit_placeholder}`",
        f"**Q028 regression:** `{'PASS' if report.q028_all_passed else 'FAIL'}`",
        f"**Machine locator coverage:** `{report.locator_coverage:.0%}`",
        f"**Machine all ok:** `{report.machine_all_ok}`",
        f"**Human signoff complete:** `{report.human_signoff_complete}`",
        "",
        f"> Ready blocked: {report.ready_blocked_reason}",
        "",
        "| case_id | claim_id | evidence_id | locator? | quote? | machine_ok | human_signoff | notes |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in report.rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    row.case_id,
                    row.claim_id,
                    row.evidence_id,
                    str(row.has_locator),
                    str(row.quote_nonempty),
                    str(row.machine_ok),
                    row.human_signoff,
                    row.notes.replace("|", "/"),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Human signoff (required before Ready)",
            "",
            "- Reviewer name: ______________",
            "- Date: ______________",
            "- Statement: I verified key facts have original-text locators for the rows above.",
            "- Signature: ______________",
            "",
            "## Boundaries",
            "",
            "- PAIRING_STRUCTURE=STRUCTURE_OK",
            "- ACTUAL_RELEVANCE_GOLD=NOT_READY",
            "- FORMAL_RETRIEVAL_METRICS_AUTHORIZED=false",
            "- Do not Ready/Merge until T09 revalidation and captain authorization.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def write_signoff_artifacts(
    *,
    output_md: Path,
    output_json: Path,
    git_commit: str,
    gold_path: Path = DEFAULT_GOLD_PATH,
) -> WaveCSignoffReport:
    """
    写出签字表 Markdown 与 JSON 工件。

    参数：
        output_md / output_json: 输出路径。
        git_commit: HEAD。
        gold_path: gold 路径。

    返回：
        WaveCSignoffReport。
    """
    report = build_wave_c_signoff_report(
        gold_path=gold_path,
        git_commit=git_commit,
    )
    output_md.write_text(render_signoff_markdown(report), encoding="utf-8")
    output_json.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report
