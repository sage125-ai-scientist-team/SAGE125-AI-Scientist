"""
T01 Wave C：契约回归与真实来源签字材料分离红灯。
"""

from pathlib import Path

import pytest

from app.evidence.wave_c_signoff import (
    DEFAULT_REVIEWED_SUBJECT_SHA,
    build_separated_signoff_package,
    write_separated_signoff_artifacts,
)


def test_contract_and_human_rows_are_separated():
    """契约回归不得混入真实来源签字集；真实行必须可打开 DOI/路径。"""
    package = build_separated_signoff_package()
    assert package.reviewed_subject_sha == DEFAULT_REVIEWED_SUBJECT_SHA
    assert len(package.contract_regression) == 1
    assert package.contract_regression[0].machine_passed is True
    assert (
        package.contract_regression[0].classification
        == "contract_layer_not_human_source_signoff"
    )
    assert len(package.human_source_rows) == 5
    assert package.machine_precheck_all_ok is True
    assert package.human_signoff_complete is False
    for row in package.human_source_rows:
        assert row.claim_id.startswith("EVAL-CLAIM-")
        assert row.doi
        assert row.source_url.startswith("https://")
        assert row.repo_xml_path.startswith("docs/modules/T01/eval_gold/")
        assert row.quote_found_in_repo_xml is True
        assert row.provisional is False
        assert row.fixture is False
        assert row.human_signoff == "pending"


def test_rejects_harness_fixture_ids():
    """harness provisional fixture 不得进入真实签字集。"""
    with pytest.raises(KeyError):
        build_separated_signoff_package(human_claim_ids=["CLAIM-013"])


def test_write_artifacts_without_auto_signature(tmp_path: Path):
    """写出工件时不得自动填充人工签字。"""
    package = write_separated_signoff_artifacts(
        contract_md=tmp_path / "contract.md",
        human_md=tmp_path / "human.md",
        package_json=tmp_path / "pkg.json",
    )
    human = (tmp_path / "human.md").read_text(encoding="utf-8")
    assert "reviewed_subject_sha" in human
    assert "EVAL-CLAIM-001" in human
    assert "______________" in human
    assert package.human_signature == ""
    contract = (tmp_path / "contract.md").read_text(encoding="utf-8")
    assert "NOT human source signoff" in contract
