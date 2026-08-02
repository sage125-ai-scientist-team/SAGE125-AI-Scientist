"""
T01 eval_gold 包脚手架与正式 actual-gold 门禁测试。

覆盖：
    - STRUCTURE / ACTUAL_GOLD 校验；
    - harness fixture 明确排除；
    - 不宣称已纳入正式 corpus。
"""

import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE = REPO_ROOT / "docs" / "modules" / "T01" / "eval_gold" / "v1"
_SCRIPT = REPO_ROOT / "scripts" / "t01" / "validate_eval_gold.py"


def _load_validator():
    """
    动态加载校验脚本模块。

    返回：
        已加载模块。
    """
    spec = importlib.util.spec_from_file_location("validate_eval_gold", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_eval_gold_actual_gold_ok():
    """
    正式提交包应通过 --require-ready，且每条 pair 非 provisional。
    """
    mod = _load_validator()
    mod.write_checksums(PACKAGE)
    assert mod.validate_package(PACKAGE, require_ready=True) == 0
    pairs = json.loads((PACKAGE / "pairs.json").read_text(encoding="utf-8"))["pairs"]
    assert len(pairs) >= 1
    for pair in pairs:
        assert pair["provisional"] is False
        assert pair["synthetic"] is False
        assert pair["fixture"] is False
        assert pair["evaluation_tier"] == "actual_gold"
        assert pair.get("source_uri")
        assert pair.get("license_or_authorization")
        assert pair.get("source_file_sha256", {}).get("xml")


def test_harness_gold_is_explicitly_excluded_in_manifest():
    """
    manifest 必须明确排除 harness evidence_gold_set.json。
    """
    mod = _load_validator()
    mod.write_checksums(PACKAGE)
    manifest = json.loads((PACKAGE / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["ready_for_t09_formal_eval"] is True
    assert manifest["not_synthetic_provisional_fixture"] is True
    excluded = manifest["explicit_exclusion"]["harness_gold_path"]
    assert excluded == "docs/modules/T01/evidence_gold_set.json"
    assert "NOT_CLAIMED" in manifest.get("corpus_inclusion_status", "")
    assert (PACKAGE / "checksums.sha256").is_file()


def test_source_xml_snapshots_exist_with_index():
    """
    受控 sources 目录应含 XML 快照与索引。
    """
    index = json.loads(
        (PACKAGE / "sources" / "SOURCES_INDEX.json").read_text(encoding="utf-8")
    )
    assert len(index) >= 4
    for row in index:
        xml_path = PACKAGE / "sources" / f"{row['pmcid']}.xml"
        assert xml_path.is_file()
        assert row.get("pdf_sha256")
        assert row.get("xml_sha256")
        assert str(row.get("license", "")).lower().startswith("cc")
