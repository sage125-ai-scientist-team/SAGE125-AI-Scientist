"""
tests/test_extract_questions.py — 125 问题抽取测试。

覆盖（仅当 data/raw/sjtu-booklet.pdf 存在时运行，否则跳过）：
    - 运行抽取脚本后 questions_125.json 存在；
    - 至少包含 "Can we predict the next pandemic?"；
    - 每项含 id/domain/question/source_page；
    - 关键跨栏问题的断句、领域和摘录语义正确；
    - extraction_report.md 只有在数量与语义质量门均通过时才含 PASS。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# 项目根与关键路径。
ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = ROOT / "data" / "raw" / "sjtu-booklet.pdf"
JSON_PATH = ROOT / "data" / "processed" / "questions_125.json"
REPORT_PATH = ROOT / "data" / "processed" / "extraction_report.md"

# PDF 不存在则跳过整个模块（抽取依赖真实 PDF）。
pytestmark = pytest.mark.skipif(not PDF_PATH.exists(), reason="缺少 data/raw/sjtu-booklet.pdf")


def _ensure_extracted():
    """若尚未生成 questions_125.json，则运行抽取主流程生成。"""
    # 已存在则复用，避免重复抽取。
    if JSON_PATH.exists():
        return
    # 导入并运行抽取脚本主函数。
    import scripts.extract_125_questions as extractor

    extractor.main()


def test_questions_json_exists_and_valid():
    """抽取后 JSON 存在，且每项字段完整、含 pandemic 问题。"""
    _ensure_extracted()
    assert JSON_PATH.exists()
    items = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    # 至少包含关键 demo 问题。
    assert any("predict the next pandemic" in it["question"].lower() for it in items)
    # 每项字段完整。
    for it in items:
        assert it.get("id")
        assert it.get("domain")
        assert it.get("question")
        assert "source_page" in it


def test_known_cross_column_questions_are_semantically_correct():
    """已知双栏错拼项必须保持稳定 Q 编号，且题目/领域/摘录各自对应。"""
    _ensure_extracted()
    items = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    by_id = {item["id"]: item for item in items}

    assert by_id["Q004"]["domain"] == "Mathematical Sciences"
    assert "riemann" in by_id["Q004"]["booklet_excerpt"].lower()
    assert "zeta" in by_id["Q004"]["booklet_excerpt"].lower()

    assert by_id["Q018"]["question"] == "How will the next generation of vaccines be made?"
    assert "vaccine" in by_id["Q018"]["booklet_excerpt"].lower()
    assert "meridian" not in by_id["Q018"]["booklet_excerpt"].lower()
    assert by_id["Q019"]["question"] == (
        "Is there a scientific basis to the Meridian System in traditional Chinese medicine?"
    )
    assert "acupuncture" in by_id["Q019"]["booklet_excerpt"].lower()

    assert by_id["Q121"]["question"] == "Will artificial intelligence replace humans?"
    assert "uncertainty" in by_id["Q121"]["booklet_excerpt"].lower()
    assert "nanobot" not in by_id["Q121"]["booklet_excerpt"].lower()

    assert by_id["Q122"]["question"] == (
        "Could we integrate with computers to form a human–machine hybrid species?"
    )
    assert "exoskeleton" in by_id["Q122"]["booklet_excerpt"].lower()
    assert by_id["Q123"]["question"] == (
        "Can quantum artificial intelligence imitate the human brain?"
    )
    assert "quantum" in by_id["Q123"]["booklet_excerpt"].lower()


def test_semantic_validator_rejects_count_preserving_corruption():
    """即使仍有 125 条，领域错配、跨栏粘连和残句也必须使质量门失败。"""
    _ensure_extracted()
    from scripts.extract_125_questions import validate_question_items

    items = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    items[3]["domain"] = "Chemistry"
    items[17]["question"] = (
        "How will the next generation of vaccines be Is there a scientific basis to the Meridian made?"
    )
    items[122]["question"] = "the human brain?"

    issues = validate_question_items(items)
    joined = "\n".join(issues)
    assert "Q004" in joined and "领域错配" in joined
    assert "Q018" in joined and "粘连" in joined
    assert "Q123" in joined and "残句" in joined


def test_layout_repair_is_repeatable_and_preserves_record_count():
    """对典型 PyMuPDF 错拼输入重复校正，结果应幂等且不改变记录数。"""
    from scripts.extract_125_questions import repair_known_layout_anomalies

    broken = [
        {
            "question": "Is the Riemann hypothesis true?",
            "domain": "Chemistry",
            "source_page": 7,
            "booklet_excerpt": "Riemann zeta function",
        },
        {
            "question": (
                "How will the next generation of vaccines be Is there a scientific basis "
                "to the Meridian made?"
            ),
            "domain": "Medicine & Health",
            "source_page": 12,
            "booklet_excerpt": "",
        },
        {
            "question": "System in traditional Chinese medicine?",
            "domain": "Medicine & Health",
            "source_page": 12,
            "booklet_excerpt": "vaccine Meridian interleaving",
        },
        {
            "question": "Will artificial intelligence replace humans?",
            "domain": "Artificial Intelligence",
            "source_page": 41,
            "booklet_excerpt": "AI uncertainty. Nanobot continuation.",
        },
        {
            "question": (
                "Could we integrate with computers to form Can quantum artificial intelligence "
                "imitate a human–machine hybrid species?"
            ),
            "domain": "Artificial Intelligence",
            "source_page": 42,
            "booklet_excerpt": "",
        },
        {
            "question": "the human brain?",
            "domain": "Artificial Intelligence",
            "source_page": 42,
            "booklet_excerpt": "hybrid brain interleaving",
        },
    ]

    original_count = len(broken)
    first_repairs = repair_known_layout_anomalies(broken)
    snapshot = json.dumps(broken, ensure_ascii=False, sort_keys=True)
    second_repairs = repair_known_layout_anomalies(broken)

    assert len(broken) == original_count
    assert {"riemann", "vaccines", "meridian", "ai_replace", "hybrid", "quantum_brain"} <= set(first_repairs)
    assert second_repairs == []
    assert json.dumps(broken, ensure_ascii=False, sort_keys=True) == snapshot


def test_extraction_report_status():
    """报告存在，且依据完整质量门而非仅数量标记 PASS/WARNING。"""
    _ensure_extracted()
    from scripts.extract_125_questions import validate_question_items

    assert REPORT_PATH.exists()
    report = REPORT_PATH.read_text(encoding="utf-8")
    items = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    if not validate_question_items(items):
        assert "PASS" in report
    else:
        assert "WARNING" in report
