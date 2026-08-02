"""
T01 eval_gold 包脚手架与门禁测试。

脚手架必须 STRUCTURE_OK；宣称 ready 但无 actual pairs 必须失败。
"""

import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE = REPO_ROOT / "docs" / "modules" / "T01" / "eval_gold" / "v1"
_SCRIPT = REPO_ROOT / "scripts" / "t01" / "validate_eval_gold.py"


def _load_validator():
    """动态加载校验脚本模块。"""
    spec = importlib.util.spec_from_file_location("validate_eval_gold", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_eval_gold_scaffold_structure_ok():
    """脚手架包通过结构校验，且不得宣称正式评测就绪。"""
    mod = _load_validator()
    mod.write_checksums(PACKAGE)
    assert mod.validate_package(PACKAGE, require_ready=False) == 0
    assert mod.validate_package(PACKAGE, require_ready=True) == 1


def test_harness_gold_is_explicitly_excluded_in_manifest():
    """manifest 必须明确排除 harness evidence_gold_set.json。"""
    mod = _load_validator()
    mod.write_checksums(PACKAGE)
    manifest = json.loads((PACKAGE / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["ready_for_t09_formal_eval"] is False
    assert manifest["not_synthetic_provisional_fixture"] is False
    excluded = manifest["explicit_exclusion"]["harness_gold_path"]
    assert excluded == "docs/modules/T01/evidence_gold_set.json"
    assert (PACKAGE / "checksums.sha256").is_file()
