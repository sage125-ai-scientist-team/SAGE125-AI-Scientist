"""
T01 Wave C 08/08：关键事实 locator 机器核验与签字表生成。
"""

from pathlib import Path

from app.evidence.wave_c_signoff import (
    build_wave_c_signoff_report,
    render_signoff_markdown,
    write_signoff_artifacts,
)


def test_wave_c_signoff_machine_rows_have_locators():
    """关键事实行（Q028+旗舰+3随机）机器核验应全部通过。"""
    report = build_wave_c_signoff_report(git_commit="TEST-HEAD")
    assert report.q028_all_passed is True
    assert len(report.rows) == 5
    assert report.machine_all_ok is True
    assert report.locator_coverage == 1.0
    assert report.human_signoff_complete is False
    assert all(row.human_signoff == "pending" for row in report.rows)


def test_wave_c_signoff_artifacts_written(tmp_path: Path):
    """签字表 md/json 可写出且不伪装人工已签。"""
    md = tmp_path / "signoff.md"
    js = tmp_path / "signoff.json"
    report = write_signoff_artifacts(
        output_md=md,
        output_json=js,
        git_commit="TEST-HEAD",
    )
    text = md.read_text(encoding="utf-8")
    assert "human_signoff" in text
    assert "pending" in text
    assert "Ready blocked" in text
    assert report.to_dict()["pairing_boundary"]["ACTUAL_RELEVANCE_GOLD"] == "NOT_READY"
    assert "TEST-HEAD" in render_signoff_markdown(report)
