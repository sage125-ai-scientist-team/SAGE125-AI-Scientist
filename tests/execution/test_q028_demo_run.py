"""Q028 UI demo run must not depend on a D-drive-only offline cache."""

from __future__ import annotations

from pathlib import Path

from app.execution import q028_demo_run
from app.execution.datasets import get_default_dataset_registry


def test_demo_cache_root_uses_data_dir_not_legacy_d_path(tmp_path, monkeypatch):
    monkeypatch.delenv("SAGE125_WDBC_CACHE_ROOT", raising=False)
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "runtime-data"))
    root = q028_demo_run.resolve_demo_cache_root()
    assert root == tmp_path / "runtime-data" / "cache" / "t05-wdbc"
    assert "preserved_from_d_root" not in str(root)


def test_demo_cache_root_honors_explicit_override(tmp_path, monkeypatch):
    override = tmp_path / "explicit-cache"
    monkeypatch.setenv("SAGE125_WDBC_CACHE_ROOT", str(override))
    assert q028_demo_run.resolve_demo_cache_root() == override


def test_missing_cache_does_not_force_offline(tmp_path):
    assert q028_demo_run.pinned_cache_available(tmp_path) is False


def test_existing_pin_sized_file_is_treated_as_cache(tmp_path):
    path = q028_demo_run._pinned_wdbc_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"x" * q028_demo_run.WDBC_PIN_SIZE_BYTES)
    assert q028_demo_run.pinned_cache_available(tmp_path) is True


def test_default_wdbc_allows_official_uci_cdn_redirect():
    definition = get_default_dataset_registry().get("uci-wdbc-diagnostic-17-1995-10-31")
    assert "archive.ics.uci.edu" in definition.allowed_source_hosts
    assert "download.ics.uci.edu" in definition.allowed_redirect_hosts


def test_demo_run_source_does_not_hardcode_offline_true():
    source = Path(q028_demo_run.__file__).read_text(encoding="utf-8")
    assert "offline=True" not in source
    assert "resolve_demo_cache_root" in source
    assert "DATA_DIR" in source
