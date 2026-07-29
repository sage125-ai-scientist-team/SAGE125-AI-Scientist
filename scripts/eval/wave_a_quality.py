"""Wave A 可执行质量契约检查，不访问网络、环境密钥或运行数据。"""

from __future__ import annotations

import argparse
import ast
import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OWNER_ROOTS = (ROOT / "scripts" / "eval", ROOT / "tests" / "integration")


def python_files() -> list[Path]:
    """返回 Wave A 自有路径中受基础 lint/type 契约约束的 Python 文件。"""
    return sorted(path for root in OWNER_ROOTS for path in root.rglob("*.py"))


def lint() -> int:
    """执行无第三方依赖的基础源文件完整性与尾随空白检查。"""
    failures: list[str] = []
    for path in python_files():
        source = path.read_text(encoding="utf-8")
        try:
            ast.parse(source, filename=str(path))
        except SyntaxError as exc:
            failures.append(f"syntax:{path.relative_to(ROOT)}:{exc.lineno}")
        failures.extend(
            f"trailing-whitespace:{path.relative_to(ROOT)}:{number}"
            for number, line in enumerate(source.splitlines(), start=1)
            if line.rstrip() != line
        )
    print(json.dumps({"check": "wave_a_lint", "files": len(python_files()), "failures": failures}))
    return int(bool(failures))


def types() -> int:
    """验证 Wave A 公共函数的参数和返回值均具有注解。"""
    failures: list[str] = []
    for path in python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name.startswith("_"):
                continue
            arguments = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
            if node.args.vararg:
                arguments.append(node.args.vararg)
            if node.args.kwarg:
                arguments.append(node.args.kwarg)
            if node.returns is None or any(arg.annotation is None for arg in arguments):
                failures.append(f"unannotated:{path.relative_to(ROOT)}:{node.name}")
    print(json.dumps({"check": "wave_a_type_contract", "failures": failures}))
    return int(bool(failures))


def validate_result(path: Path) -> int:
    """验证 benchmark dry-run 输出具有约定 JSON 与 CSV 字段且没有伪造分数。"""
    payload = json.loads(path.read_text(encoding="utf-8"))
    required = {"mode", "seed", "input_manifest", "variants", "status"}
    failures = [f"missing:{key}" for key in sorted(required - payload.keys())]
    if payload.get("status") != "planned":
        failures.append("status-must-be-planned")
    if any("score" in variant or "metric" in variant for variant in payload.get("variants", [])):
        failures.append("dry-run-must-not-contain-scores")
    csv_path = path.with_suffix(".csv")
    if not csv_path.exists():
        failures.append("missing-csv")
    else:
        with csv_path.open(encoding="utf-8", newline="") as handle:
            fields = csv.DictReader(handle).fieldnames or []
        if fields != ["variant", "mode", "seed", "input_manifest", "status"]:
            failures.append("invalid-csv-schema")
    print(json.dumps({"check": "benchmark_schema", "failures": failures}))
    return int(bool(failures))


def main() -> int:
    """解析子命令并以非零退出状态报告质量契约失败。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("lint", "type", "validate-result"))
    parser.add_argument("--result", type=Path)
    args = parser.parse_args()
    if args.command == "lint":
        return lint()
    if args.command == "type":
        return types()
    if args.result is None:
        parser.error("--result is required for validate-result")
    return validate_result(args.result)


if __name__ == "__main__":
    raise SystemExit(main())
