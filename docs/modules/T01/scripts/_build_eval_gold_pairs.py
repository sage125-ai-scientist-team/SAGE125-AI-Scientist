"""
从已下载的 CC-BY PMC 全文构建 T01 eval_gold pairs.json，并回填 manifest。

说明：
    - 仅使用仓库内 sources/*.xml 中可定位的原文片段；
    - 不覆盖 evidence_gold_set.json；
    - corpus 纳入声明保持 pending（由 T09/组长确认）。
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

def _repo_root() -> Path:
    """定位仓库根（含 .git）。"""
    cur = Path(__file__).resolve().parent
    while cur != cur.parent:
        if (cur / ".git").exists():
            return cur
        cur = cur.parent
    raise RuntimeError("repository root not found")


REPO = _repo_root()
PACKAGE = REPO / "docs" / "modules" / "T01" / "eval_gold" / "v1"
SOURCES = PACKAGE / "sources"


def sha256_text(text: str) -> str:
    """
    计算规范化 quote 的 SHA-256。

    参数：
        text: 引文字符串。

    返回：
        ``sha256:<hex>``。
    """
    normalized = re.sub(r"\s+", " ", text.strip())
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def xml_plain(pmcid: str) -> str:
    """
    读取 PMC XML 并去标签为纯文本。

    参数：
        pmcid: PMC 编号。

    返回：
        空白折叠后的纯文本。
    """
    xml = (SOURCES / f"{pmcid}.xml").read_text(encoding="utf-8", errors="replace")
    text = re.sub(r"<[^>]+>", " ", xml)
    return re.sub(r"\s+", " ", text)


def assert_quote_in_source(pmcid: str, quote: str) -> None:
    """
    断言 quote 出现在源 XML 纯文本中。

    参数：
        pmcid: PMC 编号。
        quote: 待核验引文。

    异常：
        AssertionError: 引文不在源中。
    """
    plain = xml_plain(pmcid)
    needle = re.sub(r"\s+", " ", quote.strip())
    assert needle in plain, f"quote not found in {pmcid}: {needle[:80]}..."


def git_head() -> str:
    """
    读取当前 HEAD commit。

    返回：
        commit sha 或 unknown。
    """
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(REPO),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return "unknown"


def load_source_meta(pmcid: str) -> dict:
    """
    加载 sources/*.meta.json。

    参数：
        pmcid: PMC 编号。

    返回：
        meta dict。
    """
    return json.loads(
        (SOURCES / f"{pmcid}.meta.json").read_text(encoding="utf-8-sig")
    )


def make_pair(
    *,
    claim_id: str,
    claim: str,
    evidence_id: str,
    pmcid: str,
    quote: str,
    locator: dict,
    relation: str,
    expected_decision: str,
    domain: str,
    linked_question_id: str,
    bad_cite_class: str | None = None,
) -> dict:
    """
    组装单条 actual-gold pair。

    参数：
        claim_id: 主张 ID。
        claim: 主张文本。
        evidence_id: 证据 ID。
        pmcid: 源 PMC。
        quote: 原文摘录。
        locator: 定位信息。
        relation: supports/refutes/irrelevant 等。
        expected_decision: allow/degrade/block。
        domain: 领域。
        linked_question_id: 领域审计问题 ID。
        bad_cite_class: 可选坏引用类。

    返回：
        pair dict。
    """
    assert_quote_in_source(pmcid, quote)
    meta = load_source_meta(pmcid)
    authors = [a.strip() for a in str(meta.get("authors") or "").split(",") if a.strip()]
    pair = {
        "claim_id": claim_id,
        "claim": claim,
        "evidence_id": evidence_id,
        "source_id": pmcid,
        "source_type": "paper",
        "source_uri": meta["source_uri"],
        "pmcid": pmcid,
        "data_version": f"europepmc-xml+publisher-pdf@retrieved_{meta['retrieved_at_utc'][:10]}",
        "license_or_authorization": (
            f"CC-BY (Europe PMC license field={meta.get('license')}; "
            f"Open Access={meta.get('isOpenAccess')}). "
            "Short excerpts included under CC-BY with attribution; "
            "full PDF available via reproduce commands in REPRODUCE.md / meta.json."
        ),
        "quote": quote,
        "locator": locator,
        "authors": authors,
        "year": int(meta["pubYear"]) if str(meta.get("pubYear") or "").isdigit() else None,
        "doi": meta["doi"],
        "url": meta["source_uri"],
        "content_hash": sha256_text(quote),
        "source_file_sha256": {
            "pdf": meta["pdf_sha256"],
            "xml": meta["xml_sha256"],
            "pdf_path": meta["pdf_path"],
            "xml_path": meta["xml_path"],
        },
        "relation": relation,
        "expected_decision": expected_decision,
        "domain": domain,
        "linked_question_id": linked_question_id,
        "provisional": False,
        "synthetic": False,
        "fixture": False,
        "evaluation_tier": "actual_gold",
        "annotator": "Yqqxz",
        "annotated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "corpus_inclusion_status": "submitted_for_t09_provenance_review_not_in_formal_corpus",
    }
    if bad_cite_class:
        pair["bad_cite_class"] = bad_cite_class
    return pair


def build_pairs() -> list[dict]:
    """
    构建跨领域 actual-gold pairs（allow/degrade/block）。

    返回：
        pairs 列表。
    """
    # Quotes verified against Europe PMC fullTextXML snapshots in sources/.
    pairs = [
        make_pair(
            claim_id="EVAL-CLAIM-001",
            claim=(
                "Soils are a primordial compartment of terrestrial ecosystems and form "
                "the interface between the mineral earth layer and the biosphere."
            ),
            evidence_id="EVAL-EV-001",
            pmcid="PMC2082661",
            quote=(
                "Soils constitute a primordial compartment of terrestrial ecosystems. "
                "They are the interface between earth mineral layer and the biosphere."
            ),
            locator={
                "document": "PMC2082661 fullTextXML",
                "section": "Introduction",
                "doi": "10.1371/journal.pone.0001248",
            },
            relation="supports",
            expected_decision="allow",
            domain="earth_science",
            linked_question_id="Q035",
        ),
        make_pair(
            claim_id="EVAL-CLAIM-002",
            claim=(
                "A hybrid Jupyter–Galaxy platform can combine common biomedical analysis "
                "pathways with interactive data exploration."
            ),
            evidence_id="EVAL-EV-002",
            pmcid="PMC5444614",
            quote=(
                "Here, we describe a hybrid platform combining common analysis pathways "
                "with the ability to explore data interactively."
            ),
            locator={
                "document": "PMC5444614 fullTextXML",
                "section": "Abstract",
                "doi": "10.1371/journal.pcbi.1005425",
            },
            relation="supports",
            expected_decision="allow",
            domain="computer_science",
            linked_question_id="Q042",
        ),
        make_pair(
            claim_id="EVAL-CLAIM-003",
            claim=(
                "ISRIB reverses translational effects of eIF2α phosphorylation and can "
                "induce rapid disassembly of pre-formed stress granules."
            ),
            evidence_id="EVAL-EV-003",
            pmcid="PMC4341466",
            quote=(
                "ISRIB substantially reversed the translational effects elicited by "
                "phosphorylation of eIF2α and induced no major changes in translation "
                "or mRNA levels in unstressed cells."
            ),
            locator={
                "document": "PMC4341466 fullTextXML",
                "section": "Abstract",
                "doi": "10.7554/elife.05033",
            },
            relation="supports",
            expected_decision="allow",
            domain="biology",
            linked_question_id="Q024",
        ),
        make_pair(
            claim_id="EVAL-CLAIM-004",
            claim=(
                "Neuroscience research has emphasized detailed implementations of "
                "computation such as neural codes, dynamics, and circuits."
            ),
            evidence_id="EVAL-EV-004",
            pmcid="PMC5021692",
            quote=(
                "Neuroscience has focused on the detailed implementation of computation, "
                "studying neural codes, dynamics and circuits."
            ),
            locator={
                "document": "PMC5021692 fullTextXML",
                "section": "Abstract",
                "doi": "10.3389/fncom.2016.00094",
            },
            relation="supports",
            expected_decision="allow",
            domain="neuroscience",
            linked_question_id="Q077",
        ),
        make_pair(
            claim_id="EVAL-CLAIM-005",
            claim=(
                "Ring vaccination with oral cholera vaccine around cholera cases can "
                "target contacts at elevated infection risk."
            ),
            evidence_id="EVAL-EV-005",
            pmcid="PMC5021260",
            quote=(
                "Vaccinating a buffer of individuals around a case (ring vaccination) "
                "has the potential to target those who are at highest risk of infection, "
                "reducing the number of doses needed to control a disease."
            ),
            locator={
                "document": "PMC5021260 fullTextXML",
                "section": "Abstract/Introduction",
                "doi": "10.1371/journal.pmed.1002120",
            },
            relation="supports",
            expected_decision="allow",
            domain="medicine",
            linked_question_id="Q028",
        ),
        make_pair(
            claim_id="EVAL-CLAIM-006",
            claim=(
                "Because ISRIB reverses eIF2α phosphorylation effects in the reported "
                "assays, it can be assumed to cure all human cancers."
            ),
            evidence_id="EVAL-EV-006",
            pmcid="PMC4341466",
            quote=(
                "ISRIB substantially reversed the translational effects elicited by "
                "phosphorylation of eIF2α and induced no major changes in translation "
                "or mRNA levels in unstressed cells."
            ),
            locator={
                "document": "PMC4341466 fullTextXML",
                "section": "Abstract",
                "doi": "10.7554/elife.05033",
            },
            relation="supports",
            expected_decision="degrade",
            domain="medicine",
            linked_question_id="Q028",
            bad_cite_class="OVERGENERALIZATION",
        ),
        make_pair(
            claim_id="EVAL-CLAIM-007",
            claim=(
                "Climate carbon-cycle feedback parameters can be directly inferred from "
                "a neuroscience deep-learning integration review alone."
            ),
            evidence_id="EVAL-EV-007",
            pmcid="PMC5021692",
            quote=(
                "Neuroscience has focused on the detailed implementation of computation, "
                "studying neural codes, dynamics and circuits."
            ),
            locator={
                "document": "PMC5021692 fullTextXML",
                "section": "Abstract",
                "doi": "10.3389/fncom.2016.00094",
            },
            relation="irrelevant",
            expected_decision="degrade",
            domain="climate",
            linked_question_id="Q089",
            bad_cite_class="CROSS_DOMAIN",
        ),
        make_pair(
            claim_id="EVAL-CLAIM-008",
            claim=(
                "Soil ecology publication patterns prove that every terrestrial nutrient "
                "cycle is fully explained by Jupyter notebooks."
            ),
            evidence_id="EVAL-EV-008",
            pmcid="PMC2082661",
            quote=(
                "Soils constitute a primordial compartment of terrestrial ecosystems. "
                "They are the interface between earth mineral layer and the biosphere."
            ),
            locator={
                "document": "PMC2082661 fullTextXML",
                "section": "Introduction",
                "doi": "10.1371/journal.pone.0001248",
            },
            relation="irrelevant",
            expected_decision="block",
            domain="methodology",
            linked_question_id="Q042",
            bad_cite_class="UNSUPPORTED_CLAIM",
        ),
    ]
    return pairs


def write_package(pairs: list[dict]) -> None:
    """
    写入 pairs.json 与更新后的 manifest.json。

    参数：
        pairs: actual-gold pairs。
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    pairs_doc = {
        "schema_version": "t01-eval-gold-pairs-v1",
        "package_id": "t01-eval-gold-v1",
        "evaluation_tier": "actual_gold_submitted_for_t09_review",
        "note": (
            "Human-curated CC-BY open-access excerpts with pinned source SHA-256. "
            "NOT a declaration of formal corpus inclusion; T09 validates provenance; "
            "captain confirms corpus admission. Harness fixture "
            "docs/modules/T01/evidence_gold_set.json remains untouched and excluded."
        ),
        "pair_count": len(pairs),
        "pairs": pairs,
    }
    (PACKAGE / "pairs.json").write_text(
        json.dumps(pairs_doc, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    manifest = json.loads((PACKAGE / "manifest.json").read_text(encoding="utf-8"))
    index = []
    for meta_path in sorted(SOURCES.glob("PMC*.meta.json")):
        row = json.loads(meta_path.read_text(encoding="utf-8-sig"))
        if row.get("doi"):
            index.append(row)
    (SOURCES / "SOURCES_INDEX.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    provenance = dict(manifest.get("provenance") or {})
    provenance.update(
        {
            "source_uri": (
                "https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/"
                "tree/HEAD/docs/modules/T01/eval_gold/v1"
            ),
            "data_version": f"v1-actual-gold-submitted-{now[:10]}",
            "license_or_authorization": (
                "Per-pair CC-BY open-access publisher licenses (see pairs.json and "
                "sources/*.meta.json). Package schema/scripts follow repository license. "
                "Excerpts attributed; redistribution of full PDFs follows each publisher CC-BY terms."
            ),
            "file_sha256_catalog": "docs/modules/T01/eval_gold/v1/checksums.sha256",
            "repository_path": "docs/modules/T01/eval_gold/v1",
            "controlled_artifact_path": "docs/modules/T01/eval_gold/v1/sources",
            "reproduce_commands_doc": "docs/modules/T01/eval_gold/v1/REPRODUCE.md",
            "reproduce_command": (
                "python docs/modules/T01/scripts/validate_eval_gold.py "
                "--package docs/modules/T01/eval_gold/v1 --write-checksums --require-ready"
            ),
            "git_commit": git_head(),
            "labels_expected_results_domain_mapping": {
                "label_fields": [
                    "expected_decision",
                    "relation",
                    "domain",
                    "linked_question_id",
                    "bad_cite_class",
                ],
                "expected_decision_enum": ["allow", "degrade", "block"],
                "domain_mapping_doc": "docs/modules/T01/domain_audit_12.json",
                "pairs_path": "docs/modules/T01/eval_gold/v1/pairs.json",
                "current_pair_count": len(pairs),
                "decision_counts": {
                    "allow": sum(1 for p in pairs if p["expected_decision"] == "allow"),
                    "degrade": sum(1 for p in pairs if p["expected_decision"] == "degrade"),
                    "block": sum(1 for p in pairs if p["expected_decision"] == "block"),
                },
            },
            "declaration_not_synthetic_provisional_fixture": (
                "TRUE for pairs in pairs.json: each pair sets provisional=false, "
                "synthetic=false, fixture=false, evaluation_tier=actual_gold. "
                "Harness evidence_gold_set.json remains provisional fixture and is excluded."
            ),
            "corpus_inclusion_status": (
                "NOT_CLAIMED_IN_FORMAL_CORPUS — submitted_for_t09_provenance_review; "
                "final admission requires T09 validation + captain confirmation."
            ),
            "source_sha256_index": "docs/modules/T01/eval_gold/v1/sources/SOURCES_INDEX.json",
        }
    )
    # Keep authoritative digests pointer
    provenance["file_sha256"] = {
        "_note": "Package file digests in checksums.sha256; source PDF/XML digests in sources/*.meta.json"
    }

    manifest.update(
        {
            "evaluation_tier": "actual_gold_submitted_for_t09_review",
            "ready_for_t09_formal_eval": True,
            "not_synthetic_provisional_fixture": True,
            "submitted_at_utc": now,
            "corpus_inclusion_status": provenance["corpus_inclusion_status"],
            "provenance": provenance,
            "status_note": (
                "Provenance-complete actual-gold submission for T09 review. "
                "Do NOT treat as already admitted to the formal corpus."
            ),
        }
    )
    (PACKAGE / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    """构建 pairs 并写回包文件。"""
    pairs = build_pairs()
    write_package(pairs)
    print(f"wrote {len(pairs)} pairs")


if __name__ == "__main__":
    main()
