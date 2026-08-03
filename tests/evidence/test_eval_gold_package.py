"""
T01 eval_gold 正式包门禁测试（只读校验路径）。
"""

import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE = REPO_ROOT / "docs" / "modules" / "T01" / "eval_gold" / "v1"
_VALIDATE = (
    REPO_ROOT / "docs" / "modules" / "T01" / "scripts" / "validate_eval_gold.py"
)
_FETCH = (
    REPO_ROOT / "docs" / "modules" / "T01" / "scripts" / "fetch_eval_gold_sources.py"
)


def _load(path: Path, name: str):
    """动态加载脚本模块。"""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_eval_gold_actual_gold_ok_readonly():
    """--require-ready 与 fetch 默认模式均应 exit 0，且不依赖 tip HEAD。"""
    validate = _load(_VALIDATE, "validate_eval_gold")
    fetch = _load(_FETCH, "fetch_eval_gold_sources")
    assert fetch.main(["--package", str(PACKAGE)]) == 0
    assert validate.validate_package(PACKAGE, require_ready=True) == 0
    pairs = json.loads((PACKAGE / "pairs.json").read_text(encoding="utf-8"))["pairs"]
    assert len(pairs) >= 1
    for pair in pairs:
        assert pair["provisional"] is False
        assert pair["synthetic"] is False
        assert pair["fixture"] is False
        assert not str(pair["claim_id"]).startswith("CLAIM-")


def test_harness_gold_excluded_and_domain_mapping_fixture_free():
    """manifest 排除 harness；domain mapping 不得依赖 CLAIM-* fixture。"""
    manifest = json.loads((PACKAGE / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["ready_for_t09_formal_eval"] is True
    assert "NOT_CLAIMED" in manifest.get("corpus_inclusion_status", "")
    assert (
        manifest["explicit_exclusion"]["harness_gold_path"]
        == "docs/modules/T01/evidence_gold_set.json"
    )
    mapping_path = PACKAGE / "domain_mapping_eval_gold.json"
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    assert mapping["depends_on_harness_fixture"] is False
    for row in mapping["mappings"]:
        for claim_id in row.get("linked_eval_claim_ids") or []:
            assert str(claim_id).startswith("EVAL-CLAIM-")
        assert not row.get("linked_gold_claim_ids")


def test_frozen_xml_matches_index_raw_bytes():
    """冻结 XML 原始字节哈希必须与 SOURCES_INDEX 一致。"""
    validate = _load(_VALIDATE, "validate_eval_gold")
    index = json.loads(
        (PACKAGE / "sources" / "SOURCES_INDEX.json").read_text(encoding="utf-8")
    )
    for row in index:
        xml_path = PACKAGE / "sources" / f"{row['pmcid']}.xml"
        assert xml_path.is_file()
        assert validate._sha256_file(xml_path) == row["xml_sha256"]
        assert "raw" in str(row.get("xml_byte_semantics", "")).lower() or row.get(
            "xml_byte_semantics"
        )
