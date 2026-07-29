"""Wave A 评测与消融 dry-run 骨架；只产生 planned 清单，不运行模型。"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


VARIANTS = ("no-RAG", "no-reviewer", "no-HITL", "single-agent", "full-system")


def build_manifest(seed: int, input_manifest: str) -> dict[str, object]:
    """构造五种固定消融配置的可审计 planned 评测清单。"""
    return {
        "mode": "mock",
        "seed": seed,
        "input_manifest": input_manifest,
        "status": "planned",
        "variants": [
            {
                "variant": variant,
                "mode": "mock",
                "status": "planned",
                "seed": seed,
                "input_manifest": input_manifest,
            }
            for variant in VARIANTS
        ],
    }


def write_manifest(output: Path, payload: dict[str, object]) -> None:
    """写入 JSON 与同 schema 的 CSV，且不写入任何评测分数。"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with output.with_suffix(".csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["variant", "mode", "seed", "input_manifest", "status"],
        )
        writer.writeheader()
        writer.writerows(payload["variants"])  # type: ignore[arg-type]


def main() -> int:
    """执行 dry-run 并输出 planned manifest 的绝对路径。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", required=True)
    parser.add_argument("--seed", type=int, default=20260810)
    parser.add_argument("--input-manifest", default="fixtures/wave_a.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = build_manifest(args.seed, args.input_manifest)
    write_manifest(args.output, payload)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
