"""
T01 Wave C 签字材料构建（契约回归 vs 真实来源人工核验分离）。

规则（T09）：
1. 使用 ``reviewed_subject_sha`` 记录被审代码/证据提交，禁止为追 tip 连续 rebind；
2. Q028 contract regression 不得计入真实原文人工签字样本；
3. 真实行必须来自可打开 DOI/URL 或仓库原文路径（eval_gold），非 harness fixture；
4. 人工姓名/日期/签字不得自动生成。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional, Sequence

from app.evidence.q028_regression import run_q028_regression

EVAL_GOLD_PAIRS = Path("docs/modules/T01/eval_gold/v1/pairs.json")
# 被人工核验针对的代码/证据冻结提交（禁止随 tip rebind）。
DEFAULT_REVIEWED_SUBJECT_SHA = (
    "344482e481398fd304782b69d62c93f6441c7b6c"
)
# 5 项真实来源样本（eval_gold；非 harness fixture）。
DEFAULT_HUMAN_CLAIM_IDS = (
    "EVAL-CLAIM-001",
    "EVAL-CLAIM-002",
    "EVAL-CLAIM-003",
    "EVAL-CLAIM-004",
    "EVAL-CLAIM-005",
)


@dataclass(frozen=True)
class ContractRegressionRow:
    """
    契约层回归行（不得当作真实原文人工签字）。

    属性：
        scenario_suite: 套件名。
        machine_passed: 机器回归是否通过。
        classification: 固定为 contract_layer_not_human_source_signoff。
        notes: 说明。
    """

    scenario_suite: str
    machine_passed: bool
    classification: str = "contract_layer_not_human_source_signoff"
    notes: str = (
        "Q028 contract-layer regression only; not a live pipeline trace; "
        "excluded from human original-text signoff sample set"
    )


@dataclass(frozen=True)
class HumanSourceRow:
    """
    真实来源人工核验行（签字前机器预检 + 人工栏）。

    属性见字段；``human_*`` 仅允许负责人手填，默认 pending/空。
    """

    row_id: str
    claim_id: str
    evidence_id: str
    claim: str
    quote: str
    doi: str
    source_url: str
    repo_xml_path: str
    repo_pdf_path: str
    locator_section: str
    locator_page: Optional[str]
    content_hash: str
    xml_sha256: str
    quote_found_in_repo_xml: bool
    provisional: bool
    fixture: bool
    verification_status: str
    human_opened_source: str = "pending"
    human_verbatim_match: str = "pending"
    human_signoff: str = "pending"
    human_notes: str = ""


@dataclass
class SeparatedSignoffPackage:
    """
    分离后的签字包。

    属性：
        reviewed_subject_sha: 被审代码/证据冻结 SHA（不追 tip）。
        contract_regression: 契约回归行列表。
        human_source_rows: 真实来源行。
        machine_precheck_all_ok: 机器预检（quote 在 XML、非 provisional/fixture）。
        human_signoff_complete: 人工是否已填完（默认 False）。
        human_reviewer_name: 人工姓名（空=未填）。
        human_review_date: 人工日期（空=未填）。
        human_signature: 人工签字（空=未填）。
        human_conclusion: 人工结论（空=未填）。
    """

    reviewed_subject_sha: str
    contract_regression: list[ContractRegressionRow] = field(default_factory=list)
    human_source_rows: list[HumanSourceRow] = field(default_factory=list)
    machine_precheck_all_ok: bool = False
    human_signoff_complete: bool = False
    human_reviewer_name: str = ""
    human_review_date: str = ""
    human_signature: str = ""
    human_conclusion: str = ""

    def to_dict(self) -> dict[str, Any]:
        """序列化为 JSON 友好 dict。"""
        return {
            "reviewed_subject_sha": self.reviewed_subject_sha,
            "artifact_commit_sha_note": (
                "Do not embed tip HEAD here; publish artifact commit SHA in PR comment only"
            ),
            "contract_regression": [asdict(row) for row in self.contract_regression],
            "human_source_rows": [asdict(row) for row in self.human_source_rows],
            "machine_precheck_all_ok": self.machine_precheck_all_ok,
            "human_signoff_complete": self.human_signoff_complete,
            "human_reviewer_name": self.human_reviewer_name,
            "human_review_date": self.human_review_date,
            "human_signature": self.human_signature,
            "human_conclusion": self.human_conclusion,
            "pairing_boundary": {
                "PAIRING_STRUCTURE": "STRUCTURE_OK",
                "ACTUAL_RELEVANCE_GOLD": "NOT_READY",
                "FORMAL_RETRIEVAL_METRICS_AUTHORIZED": False,
            },
        }


def _load_eval_pairs(path: Path = EVAL_GOLD_PAIRS) -> dict[str, dict[str, Any]]:
    """
    加载 eval_gold pairs，按 claim_id 索引。

    参数：
        path: pairs.json 路径。

    返回：
        claim_id → pair。
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    pairs = payload.get("pairs") or []
    return {str(pair["claim_id"]): pair for pair in pairs}


def _quote_in_xml(quote: str, xml_path: str) -> bool:
    """
    检查逐字 quote 是否出现在仓库冻结 XML 中。

    参数：
        quote: 原文摘录。
        xml_path: 仓库相对路径。

    返回：
        True 表示原文命中。
    """
    path = Path(xml_path)
    if not path.is_file():
        return False
    return quote in path.read_text(encoding="utf-8")


def build_separated_signoff_package(
    *,
    reviewed_subject_sha: str = DEFAULT_REVIEWED_SUBJECT_SHA,
    human_claim_ids: Sequence[str] = DEFAULT_HUMAN_CLAIM_IDS,
    eval_pairs_path: Path = EVAL_GOLD_PAIRS,
    human_reviewer_name: str = "",
    human_review_date: str = "",
    human_signature: str = "",
    human_conclusion: str = "",
) -> SeparatedSignoffPackage:
    """
    构建分离的契约回归 + 真实来源签字包。

    参数：
        reviewed_subject_sha: 冻结被审 SHA。
        human_claim_ids: 真实核验 claim 列表（默认 5 项 eval_gold）。
        eval_pairs_path: eval gold pairs。
        human_* : 仅当负责人已核对后传入；默认留空。

    返回：
        SeparatedSignoffPackage。
    """
    q028 = run_q028_regression()
    contract = [
        ContractRegressionRow(
            scenario_suite="Q028-contract-regression",
            machine_passed=q028.all_passed,
        )
    ]
    by_id = _load_eval_pairs(eval_pairs_path)
    human_rows: list[HumanSourceRow] = []
    for index, claim_id in enumerate(human_claim_ids, start=1):
        pair = by_id[claim_id]
        if pair.get("provisional") is True or pair.get("fixture") is True:
            raise ValueError(
                f"{claim_id} is provisional/fixture; cannot enter human signoff set"
            )
        xml_path = str(pair["source_file_sha256"]["xml_path"])
        pdf_path = str(pair["source_file_sha256"]["pdf_path"])
        quote = str(pair["quote"])
        locator = pair.get("locator") or {}
        found = _quote_in_xml(quote, xml_path)
        human_rows.append(
            HumanSourceRow(
                row_id=f"H{index}",
                claim_id=claim_id,
                evidence_id=str(pair["evidence_id"]),
                claim=str(pair["claim"]),
                quote=quote,
                doi=str(pair.get("doi") or ""),
                source_url=str(pair.get("url") or pair.get("source_uri") or ""),
                repo_xml_path=xml_path,
                repo_pdf_path=pdf_path,
                locator_section=str(locator.get("section") or ""),
                locator_page=(
                    str(locator["page"]) if locator.get("page") is not None else None
                ),
                content_hash=str(pair.get("content_hash") or ""),
                xml_sha256=str(pair["source_file_sha256"]["xml"]),
                quote_found_in_repo_xml=found,
                provisional=bool(pair.get("provisional")),
                fixture=bool(pair.get("fixture")),
                verification_status="machine_precheck_ok" if found else "machine_precheck_fail",
            )
        )
    machine_ok = all(
        row.quote_found_in_repo_xml
        and row.source_url
        and row.doi
        and not row.provisional
        and not row.fixture
        for row in human_rows
    )
    signed = bool(
        human_reviewer_name.strip()
        and human_review_date.strip()
        and human_signature.strip()
        and human_conclusion.strip()
    )
    return SeparatedSignoffPackage(
        reviewed_subject_sha=reviewed_subject_sha,
        contract_regression=contract,
        human_source_rows=human_rows,
        machine_precheck_all_ok=machine_ok,
        human_signoff_complete=signed,
        human_reviewer_name=human_reviewer_name,
        human_review_date=human_review_date,
        human_signature=human_signature,
        human_conclusion=human_conclusion,
    )


def render_contract_regression_markdown(package: SeparatedSignoffPackage) -> str:
    """
    渲染契约回归报告（明确排除出人工签字集）。

    参数：
        package: SeparatedSignoffPackage。

    返回：
        Markdown。
    """
    lines = [
        "# T01 Wave C — Contract regression report (NOT human source signoff)",
        "",
        f"**reviewed_subject_sha:** `{package.reviewed_subject_sha}`",
        "",
        "This report is **contract-layer only**. It must **not** be counted as",
        "human original-text verification of live scientific sources.",
        "",
        "| suite | machine_passed | classification | notes |",
        "|---|---|---|---|",
    ]
    for row in package.contract_regression:
        lines.append(
            f"| {row.scenario_suite} | {row.machine_passed} | "
            f"{row.classification} | {row.notes} |"
        )
    lines.extend(
        [
            "",
            "## Reproduce",
            "",
            "```powershell",
            "python -c \"from app.evidence.q028_regression import run_q028_regression; "
            "print(run_q028_regression().to_dict())\"",
            "```",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def render_human_signoff_markdown(package: SeparatedSignoffPackage) -> str:
    """
    渲染真实来源人工签字表（签字栏默认空白）。

    参数：
        package: SeparatedSignoffPackage。

    返回：
        Markdown。
    """
    lines = [
        "# T01 Wave C — Human original-text locator signoff",
        "",
        f"**reviewed_subject_sha (frozen subject under review):** `{package.reviewed_subject_sha}`",
        "",
        "> Do **not** rebind this field to PR tip after each docs commit.",
        "> Publish the signoff **artifact commit SHA** only in the PR comment.",
        "",
        f"**Machine precheck all ok:** `{package.machine_precheck_all_ok}`",
        f"**Human signoff complete:** `{package.human_signoff_complete}`",
        "",
        "## Five human-verification rows (eval_gold actual sources)",
        "",
    ]
    for row in package.human_source_rows:
        page = row.locator_page if row.locator_page is not None else "N/A (XML section locator)"
        lines.extend(
            [
                f"### {row.row_id} — `{row.claim_id}` / `{row.evidence_id}`",
                "",
                f"- **claim:** {row.claim}",
                f"- **verbatim quote:** {row.quote}",
                f"- **DOI:** `{row.doi}`",
                f"- **source URL (openable):** {row.source_url}",
                f"- **repo XML path:** `{row.repo_xml_path}`",
                f"- **repo PDF path:** `{row.repo_pdf_path}`",
                f"- **locator.section:** `{row.locator_section}`",
                f"- **locator.page:** `{page}`",
                f"- **content_hash:** `{row.content_hash}`",
                f"- **xml_sha256:** `{row.xml_sha256}`",
                f"- **quote_found_in_repo_xml (machine):** `{row.quote_found_in_repo_xml}`",
                f"- **provisional / fixture:** `{row.provisional}` / `{row.fixture}`",
                f"- **verification_status:** `{row.verification_status}`",
                f"- **human_opened_source:** `{row.human_opened_source}`",
                f"- **human_verbatim_match:** `{row.human_verbatim_match}`",
                f"- **human_signoff (per-row):** `{row.human_signoff}`",
                "",
            ]
        )
    name = package.human_reviewer_name or "______________"
    date = package.human_review_date or "______________"
    signature = package.human_signature or "______________"
    conclusion = package.human_conclusion or "______________"
    lines.extend(
        [
            "## Human attestation (must be filled by real owner; never auto-generated)",
            "",
            "I opened each source URL and/or repo XML/PDF path above, verified the",
            "verbatim quote and locator section against the original text, and confirm",
            "these five rows are suitable as human original-text verification samples",
            "(not harness fixtures).",
            "",
            f"- **Reviewer name:** {name}",
            f"- **Date:** {date}",
            f"- **Conclusion:** {conclusion}",
            f"- **Signature:** {signature}",
            "",
            "## Boundaries",
            "",
            "- PAIRING_STRUCTURE=STRUCTURE_OK",
            "- ACTUAL_RELEVANCE_GOLD=NOT_READY",
            "- FORMAL_RETRIEVAL_METRICS_AUTHORIZED=false",
            "- Keep PR #35 OPEN / Draft until T09 revalidation and captain authorization.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def write_separated_signoff_artifacts(
    *,
    contract_md: Path,
    human_md: Path,
    package_json: Path,
    reviewed_subject_sha: str = DEFAULT_REVIEWED_SUBJECT_SHA,
    human_reviewer_name: str = "",
    human_review_date: str = "",
    human_signature: str = "",
    human_conclusion: str = "",
) -> SeparatedSignoffPackage:
    """
    写出分离的契约报告、人工签字表与 JSON。

    参数：
        contract_md / human_md / package_json: 输出路径。
        reviewed_subject_sha: 冻结被审 SHA。
        human_* : 负责人手填字段；空表示未签字。

    返回：
        SeparatedSignoffPackage。
    """
    package = build_separated_signoff_package(
        reviewed_subject_sha=reviewed_subject_sha,
        human_reviewer_name=human_reviewer_name,
        human_review_date=human_review_date,
        human_signature=human_signature,
        human_conclusion=human_conclusion,
    )
    if not package.machine_precheck_all_ok:
        raise RuntimeError("machine precheck failed for human source rows")
    contract_md.write_text(
        render_contract_regression_markdown(package),
        encoding="utf-8",
    )
    human_md.write_text(render_human_signoff_markdown(package), encoding="utf-8")
    package_json.write_text(
        json.dumps(package.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return package
