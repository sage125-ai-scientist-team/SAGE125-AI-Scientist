"""Wave B 离线 E2E 夹具：只生成 planned 清单，不调用模型或网络。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import NoReturn

from benchmark_skeleton import build_manifest, write_manifest


REQUIRED_FIELDS = frozenset(
    {"execution", "fixture_id", "input_manifest", "mode", "owner", "seed", "status"}
)
FORBIDDEN_FIELD_FRAGMENTS = ("api_key", "secret", "token", "password", "cookie", "authorization")
SUSPECTED_CREDENTIAL_VALUE = re.compile(
    r"(?:api[_-]?key|token|password|cookie|authorization)\s*[:=]|bearer\s+|sk-[A-Za-z0-9]",
    re.IGNORECASE,
)
ALLOWED_OWNER = "T09"


def fixture_error(path: Path, detail: str) -> NoReturn:
    """以可定位到输入文件与 owner 的消息拒绝不安全或无效夹具。"""
    raise ValueError(f"fixture-error:{path}:owner=T09:{detail}")


def load_fixture(path: Path) -> dict[str, object]:
    """读取并验证仅供离线 planned harness 使用的固定夹具。"""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fixture_error(path, "missing-file")
    except json.JSONDecodeError as exc:
        fixture_error(path, f"invalid-json:{exc.lineno}:{exc.colno}")
    if not isinstance(payload, dict):
        fixture_error(path, "root-must-be-object")
    fields = set(payload)
    forbidden = sorted(
        field for field in fields if any(fragment in field.lower() for fragment in FORBIDDEN_FIELD_FRAGMENTS)
    )
    if forbidden:
        fixture_error(path, f"forbidden-secret-field:{','.join(forbidden)}")
    if fields != REQUIRED_FIELDS:
        missing = sorted(REQUIRED_FIELDS - fields)
        unexpected = sorted(fields - REQUIRED_FIELDS)
        fixture_error(path, f"invalid-fields:missing={missing}:unexpected={unexpected}")
    if payload["mode"] != "mock":
        fixture_error(path, "mode-must-be-mock")
    if payload["execution"] != "offline":
        fixture_error(path, "execution-must-be-offline")
    if payload["status"] != "planned":
        fixture_error(path, "status-must-be-planned")
    if payload["owner"] != ALLOWED_OWNER:
        fixture_error(path, f"unknown-owner:{payload['owner']!r}")
    if not isinstance(payload["fixture_id"], str) or not payload["fixture_id"]:
        fixture_error(path, "fixture_id-must-be-nonempty-string")
    if not isinstance(payload["input_manifest"], str) or not payload["input_manifest"]:
        fixture_error(path, "input_manifest-must-be-nonempty-string")
    if isinstance(payload["seed"], bool) or not isinstance(payload["seed"], int):
        fixture_error(path, "seed-must-be-integer")
    for field in ("fixture_id", "input_manifest"):
        value = payload[field]
        if isinstance(value, str) and SUSPECTED_CREDENTIAL_VALUE.search(value):
            fixture_error(path, f"suspected-credential-value:{field}")
    return payload


def build_harness_manifest(fixture: dict[str, object]) -> dict[str, object]:
    """将已验证夹具转换为可由既有 Wave A schema 校验的 planned 清单。"""
    payload = build_manifest(seed=fixture["seed"], input_manifest=fixture["input_manifest"])
    payload["harness"] = {
        "fixture_id": fixture["fixture_id"],
        "owner": fixture["owner"],
        "purpose": "offline-low-cost-e2e",
    }
    return payload


def main() -> int:
    """从固定离线夹具生成稳定的 planned JSON/CSV 输出。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.fixture.resolve() == args.output.resolve():
            fixture_error(args.fixture, "output-must-not-overwrite-fixture")
        fixture = load_fixture(args.fixture)
        write_manifest(args.output, build_harness_manifest(fixture))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
