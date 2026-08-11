# -*- coding: utf-8 -*-
"""
tests/test_bootstrap_preview_data.py — Preview 题库引导脚本测试。

覆盖：
    - build_preview_seed_questions 产出 125 条且领域齐全；
    - 已知 Demo Preset 关键词可命中；
    - 每条含 preview_seed 标记，占位题含 [PREVIEW-SEED]；
    - write_preview_seed 优先写入 DATA_DIR；
    - bootstrap 在 allow_seed / APP_ENV=preview 下返回 0。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import scripts.bootstrap_preview_data as bootstrap


def test_build_preview_seed_questions_shape_and_presets():
    """
    种子题库应满足：数量 125、含 preview 标记、Demo Preset 可命中。
    """
    items = bootstrap.build_preview_seed_questions(125)
    assert len(items) == 125
    assert all(item.get("preview_seed") is True for item in items)
    assert all(item.get("label_tier") == "preview_seed" for item in items)
    domains = {item["domain"] for item in items}
    assert domains == set(bootstrap.EXPECTED_DOMAIN_COUNTS)

    blob = " ".join(item["question"].lower() for item in items)
    for keyword in ("prime", "pandemic", "climate", "creativity", "quantum"):
        assert keyword in blob, f"missing demo keyword: {keyword}"

    placeholders = [item for item in items if item["question"].startswith("[PREVIEW-SEED]")]
    assert placeholders, "应包含显式占位题"
    assert all(
        "not extracted from sjtu-booklet.pdf" in item["booklet_excerpt"].lower()
        for item in placeholders
    )


def test_write_preview_seed_prefers_data_dir(tmp_path: Path, monkeypatch):
    """
    Preview 种子必须优先写入 DATA_DIR（Render 可写区）。
    """
    data_root = tmp_path / "tmp-sage125-data"
    monkeypatch.setenv("DATA_DIR", str(data_root))
    monkeypatch.delenv("SAGE_QUESTIONS_PATH", raising=False)
    written = bootstrap.write_preview_seed(force=True)
    assert written == data_root / "processed" / "questions_125.json"
    assert written.exists()
    assert json.loads(written.read_text(encoding="utf-8"))


def test_write_preview_seed_and_bootstrap(tmp_path: Path, monkeypatch):
    """
    write_preview_seed / bootstrap 应在允许 seed 时写入 DATA_DIR。
    """
    data_root = tmp_path / "runtime-data"
    json_path = data_root / "processed" / "questions_125.json"
    monkeypatch.setenv("DATA_DIR", str(data_root))
    monkeypatch.setattr(bootstrap, "PDF_PATH", tmp_path / "missing.pdf")
    monkeypatch.delenv("SAGE_QUESTIONS_PATH", raising=False)

    written = bootstrap.write_preview_seed(force=True)
    assert written == json_path
    loaded = json.loads(json_path.read_text(encoding="utf-8"))
    assert len(loaded) == 125
    assert loaded[0]["id"] == "Q001"

    code = bootstrap.bootstrap(allow_seed=True, force_seed=False)
    assert code == 0
    assert json_path.exists()


def test_bootstrap_fails_without_seed_permission(tmp_path: Path, monkeypatch):
    """
    无 PDF 且未允许 seed 时，bootstrap 必须失败而不是静默成功。
    """
    data_root = tmp_path / "runtime-data"
    monkeypatch.setenv("DATA_DIR", str(data_root))
    monkeypatch.setattr(bootstrap, "PDF_PATH", tmp_path / "missing.pdf")
    monkeypatch.delenv("SAGE125_PREVIEW_SEED", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("PREVIEW_EPHEMERAL_STORAGE", raising=False)
    monkeypatch.delenv("SAGE_QUESTIONS_PATH", raising=False)

    code = bootstrap.bootstrap(allow_seed=False, force_seed=False)
    assert code == 2
    assert not (data_root / "processed" / "questions_125.json").exists()


def test_bootstrap_allows_seed_when_app_env_preview(tmp_path: Path, monkeypatch):
    """
    Render 已有 `APP_ENV=preview` 时，即使未设 SAGE125_PREVIEW_SEED 也应可写 seed。
    """
    data_root = tmp_path / "runtime-data"
    monkeypatch.setenv("DATA_DIR", str(data_root))
    monkeypatch.setattr(bootstrap, "PDF_PATH", tmp_path / "missing.pdf")
    monkeypatch.delenv("SAGE125_PREVIEW_SEED", raising=False)
    monkeypatch.delenv("SAGE_QUESTIONS_PATH", raising=False)
    monkeypatch.setenv("APP_ENV", "preview")

    code = bootstrap.bootstrap(allow_seed=False, force_seed=False)
    assert code == 0
    target = data_root / "processed" / "questions_125.json"
    assert target.exists()
    assert Path(os.environ["SAGE_QUESTIONS_PATH"]) == target
