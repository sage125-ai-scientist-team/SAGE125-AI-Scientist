#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
scripts/audit_project.py — 安全与真实性审计。

检查：Secret 泄露、非千问生成模型、References 真实性、Results 造假、
DeepResearch 使用、导出安全、前端安全。

运行：
    py -3 scripts/audit_project.py

返回码：全部通过=0；仅 warning=0；有 critical=1。
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# 确保项目根在 sys.path。
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.logging import get_logger

# 模块级日志器。
logger = get_logger("scripts.audit")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = PROJECT_ROOT / "exports" / "audit"

# 扫描目标目录/文件。
SCAN_DIRS = ["app", "scripts", "tests", "docs"]
# 扫描全部运行产物（含单次 run、smoke、batch、诊断）；PDF 等二进制被后缀过滤。
SCAN_EXPORT_DIRS = ["exports"]

# README 中不应出现的“已删除参赛材料脚本/产物”引用（无歧义标记，
# 避免误伤“不自动生成…”这类合法否定式免责声明）。
_README_FORBIDDEN = [
    "make_submission_bundle",
    "build_submission_docs",
    "submission_bundle.zip",
    "technical_solution.pdf",
    "demo_script_10min",
]

# ---- 检测正则 ----
# 真实 API Key（sk- 长串）。
_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{16,}"),
]
# .env 赋值中出现真实值（非空、非占位）。
_ENV_ASSIGN = re.compile(r"(DASHSCOPE_API_KEY|OPENALEX_API_KEY)\s*=\s*([A-Za-z0-9\-]{12,})")
# Windows 私有用户路径泄露。
_PRIVATE_PATH = re.compile(r"[Cc]:\\Users\\[^\\\s\"']+", re.IGNORECASE)
# 非千问模型名作为 model= 配置。
_NON_QWEN_MODEL = re.compile(
    r"model\s*=\s*[\"'][^\"']*(gpt-|claude|gemini|deepseek|kimi|glm-4|minimax)", re.IGNORECASE
)
# OpenAI 官方 endpoint。
_OPENAI_ENDPOINT = re.compile(r"api\.openai\.com", re.IGNORECASE)
# 虚构指标。
_FAKE_METRIC = re.compile(
    r"(auroc|auprc|auc|accuracy|f1|precision|recall)\s*[=:：]\s*(0?\.\d+|\d{1,3}\s*%)", re.IGNORECASE
)
# DOI 基本格式。
_DOI_PATTERN = re.compile(r"^10\.\d{4,9}/\S+$")


def _iter_source_files():
    """产出待扫描的源代码文件。"""
    for d in SCAN_DIRS:
        base = PROJECT_ROOT / d
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if p.is_file() and p.suffix in (".py", ".md", ".j2", ".css", ".txt", ".html"):
                yield p
    for f in ["README.md", "requirements.txt", ".env.example"]:
        fp = PROJECT_ROOT / f
        if fp.exists():
            yield fp


def _iter_export_files():
    """产出待扫描的导出文件。"""
    for d in SCAN_EXPORT_DIRS:
        base = PROJECT_ROOT / d
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if p.is_file() and p.suffix in (".json", ".md", ".csv", ".jsonl", ".html", ".txt"):
                yield p


def audit() -> dict:
    """执行审计，返回结果 dict。"""
    critical: list[str] = []
    warnings: list[str] = []

    # 1) .gitignore 是否忽略 .env。
    gitignore = PROJECT_ROOT / ".gitignore"
    if gitignore.exists():
        gi = gitignore.read_text(encoding="utf-8")
        if ".env" not in gi:
            critical.append(".gitignore 未忽略 .env。")
    else:
        warnings.append("未找到 .gitignore。")

    # 1b) README 范围检查：不得把项目描述为“参赛材料自动生成器”。
    readme = PROJECT_ROOT / "README.md"
    if readme.exists():
        rt = readme.read_text(encoding="utf-8", errors="ignore")
        for phrase in _README_FORBIDDEN:
            if phrase in rt:
                critical.append(f"README 含参赛材料自动生成相关措辞：{phrase}")
        # 建议包含范围声明。
        if "不是参赛材料自动生成器" not in rt:
            warnings.append("README 建议加入项目范围声明（本系统不是参赛材料自动生成器）。")

    # 2) 源码扫描：Secret / 非千问模型 / OpenAI endpoint / 私有路径。
    # 说明：tests/ 内含用于验证检测与拒绝逻辑的“故意负例”（如假密钥、非千问模型
    # 配置、官方 endpoint 字符串），不应计为 critical；关键扫描仅针对生产代码。
    for p in _iter_source_files():
        text = p.read_text(encoding="utf-8", errors="ignore")
        is_production = "tests" not in p.parts
        if not is_production:
            continue
        # Secret 扫描（生产代码不应出现长 sk- 串）。
        for pat in _SECRET_PATTERNS:
            for m in pat.finditer(text):
                critical.append(f"疑似真实 Key：{p.name}: {m.group(0)[:8]}****")
        # .env.example 允许空赋值。
        if p.name != ".env.example":
            for m in _ENV_ASSIGN.finditer(text):
                val = m.group(2)
                if val not in ("your", "xxx") and not val.startswith("你的"):
                    warnings.append(f"{p.name} 出现疑似 Key 赋值（请确认非真实）：{m.group(1)}=****")
        # 非千问模型配置与 OpenAI endpoint。
        for m in _NON_QWEN_MODEL.finditer(text):
            critical.append(f"非千问模型作为 model 配置：{p.name}: {m.group(0)}")
        if _OPENAI_ENDPOINT.search(text):
            critical.append(f"OpenAI 官方 endpoint：{p.name}")
        # 私有路径（文档/导出类文件）。
        if _PRIVATE_PATH.search(text) and p.suffix in (".md", ".json", ".txt"):
            warnings.append(f"疑似私有路径泄露：{p.name}")

    # 3) 导出扫描：Secret / 私有路径 / References / Results / DeepResearch。
    for p in _iter_export_files():
        text = p.read_text(encoding="utf-8", errors="ignore")
        for pat in _SECRET_PATTERNS:
            if pat.search(text):
                critical.append(f"导出物疑似含 Key：{p.name}")
        if _PRIVATE_PATH.search(text):
            warnings.append(f"导出物疑似私有路径：{p.name}")
        # report.json 的真实性检查。
        if p.name == "report.json":
            try:
                plan = json.loads(text)
                _audit_plan(plan, p, critical, warnings)
            except Exception:
                warnings.append(f"无法解析 {p.name}")

    passed = len(critical) == 0
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "critical": critical,
        "warnings": warnings,
    }


def _audit_plan(plan: dict, path: Path, critical: list, warnings: list) -> None:
    """对单个 ResearchPlan 做真实性检查。"""
    refs = plan.get("references", []) or []
    actual = bool(plan.get("actual_execution"))
    results = plan.get("results", "") or ""
    status = plan.get("validation_status")

    # References：DOI 格式 / mock 标记 / 空引用不得 ready。
    for r in refs:
        doi = r.get("doi")
        if doi and not _DOI_PATTERN.match(str(doi).strip()):
            critical.append(f"{path.parent.name}/report.json 非法 DOI：{doi}")
    if not refs and status == "ready_for_validation":
        critical.append(f"{path.parent.name}/report.json references 为空却 ready_for_validation。")

    # Results：无真实执行禁止虚构指标 / validated。
    if not actual:
        if _FAKE_METRIC.search(results):
            critical.append(f"{path.parent.name}/report.json 出现虚构指标。")
        if status == "validated":
            critical.append(f"{path.parent.name}/report.json validated 但无 actual_execution。")

    # DeepResearch 证据须标注需核验。
    for r in refs:
        if r.get("source_type") == "deep_research":
            note = (r.get("reliability_note") or "").lower()
            if "verification" not in note and "核验" not in note:
                warnings.append(f"{path.parent.name} DeepResearch 证据未标注需核验。")


def _write_report(result: dict) -> None:
    """写审计报告到 exports/audit/。"""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "audit_report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    md = [
        "# 项目审计报告\n",
        f"- 时间：{result['timestamp']}",
        f"- 结果：{'PASS' if result['passed'] else 'CRITICAL'}",
        f"- critical：{len(result['critical'])}",
        f"- warnings：{len(result['warnings'])}\n",
    ]
    if result["critical"]:
        md.append("## Critical\n")
        md += [f"- {c}" for c in result["critical"]]
    if result["warnings"]:
        md.append("\n## Warnings\n")
        md += [f"- {w}" for w in result["warnings"]]
    (OUT_DIR / "audit_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")


def main() -> int:
    """审计主入口。"""
    result = audit()
    _write_report(result)
    print(f"审计完成：{'PASS' if result['passed'] else 'CRITICAL'}（critical={len(result['critical'])}, warnings={len(result['warnings'])}）")
    print(f"报告：{OUT_DIR / 'audit_report.md'}")
    for c in result["critical"]:
        print("  [CRITICAL]", c)
    # 有 critical 返回 1；否则 0（含 warning）。
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
