"""
tests/test_smoke_bailian_dryrun.py — smoke_bailian --dry-run 测试（无需真实 Key）。

覆盖：dry-run 可运行、输出 smoke_report、不打印完整 Key、DeepResearch 默认 skipped。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "exports" / "smoke_bailian" / "smoke_report.json"


def test_smoke_dry_run():
    """dry-run 应成功并生成脱敏报告，DeepResearch 为 skipped。"""
    import os

    env = os.environ.copy()
    # Inherit CI/local UTF-8 mode so Chinese prints never hit Windows charmap.
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [sys.executable, "-X", "utf8", str(ROOT / "scripts" / "smoke_bailian.py"), "--dry-run"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=120,
    )
    # dry-run 返回 0。
    assert proc.returncode == 0
    assert REPORT.exists()
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    assert report["dry_run"] is True
    # DeepResearch 默认 skipped。
    assert report["deepresearch"]["ok"] is None
    # 不含完整 Key（掩码或未配置）。
    blob = json.dumps(report, ensure_ascii=False)
    assert "sk-" not in blob or "****" in report.get("dashscope_api_key_masked", "")


def test_requested_chat_failure_returns_nonzero(monkeypatch):
    """真实 chat 被明确请求且失败时，CLI 不能再返回假成功。"""
    import scripts.smoke_bailian as smoke

    settings = SimpleNamespace(
        dashscope_api_key="unit-test-key",
        workspace_id="ws-unit",
        dashscope_base_url="https://ws-unit.example.aliyuncs.com/api/v1/services/aigc/text-generation/generation",
        dashscope_deep_research_base_url="https://ws-unit.example.aliyuncs.com/api/v1",
        qwen_balanced_model="qwen3.7-plus",
        qwen_deep_research_model="qwen-deep-research",
        bailian_embedding_model="text-embedding-v4",
        bailian_rerank_model="qwen3-rerank",
        log_level="INFO",
    )
    monkeypatch.setattr(smoke, "get_settings", lambda: settings)
    monkeypatch.setattr(smoke, "_smoke_chat", lambda _settings: {"ok": False, "detail": "unit failure"})
    monkeypatch.setattr(sys, "argv", ["smoke_bailian.py", "--chat"])

    assert smoke.main() == 1
    report = json.loads(smoke.OUT_DIR.joinpath("smoke_report.json").read_text(encoding="utf-8"))
    assert report["chat"]["ok"] is False
    assert any("chat" in item for item in report["errors"])
