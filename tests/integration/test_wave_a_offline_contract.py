"""Wave A 离线 fixture：不依赖 PDF、问题清单、缓存、网络或 `.env`。"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_benchmark_dry_run_is_planned_and_schema_valid(tmp_path: Path) -> None:
    """五个消融配置在干净临时目录生成 planned JSON/CSV 且通过契约验证。"""
    output = tmp_path / "benchmark.json"
    command = [
        sys.executable,
        "scripts/eval/benchmark_skeleton.py",
        "--dry-run",
        "--seed",
        "7",
        "--input-manifest",
        "fixtures/wave_a.json",
        "--output",
        str(output),
    ]
    subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "planned"
    assert [entry["variant"] for entry in payload["variants"]] == [
        "no-RAG",
        "no-reviewer",
        "no-HITL",
        "single-agent",
        "full-system",
    ]
    assert all("score" not in entry for entry in payload["variants"])
    with output.with_suffix(".csv").open(encoding="utf-8", newline="") as handle:
        assert csv.DictReader(handle).fieldnames == [
            "variant",
            "mode",
            "seed",
            "input_manifest",
            "status",
        ]
    subprocess.run(
        [sys.executable, "scripts/eval/wave_a_quality.py", "validate-result", "--result", str(output)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
