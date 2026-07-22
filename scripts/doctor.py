#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
scripts/doctor.py — 项目本体诊断（一条命令判断系统能否跑）。

运行示例（PowerShell）：
    py -3 scripts/doctor.py
    py -3 scripts/doctor.py --mock
    py -3 scripts/doctor.py --real-check
    py -3 scripts/doctor.py --json

安全：不打印完整 API Key；不要求命令行传 Key；不输出 .env 全文。
返回码：有 critical 返回 1；仅 warning 或全 ok 返回 0。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# 确保项目根在 sys.path。
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.logging import get_logger, setup_logging

# 模块级日志器。
logger = get_logger("scripts.doctor")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = PROJECT_ROOT / "exports" / "doctor"

# 参赛材料相关文件（不应存在于本体项目）。
_FORBIDDEN_FILES = [
    "scripts/build_submission_docs.py",
    "scripts/make_submission_bundle.py",
    "app/exporters/submission_exporter.py",
    "docs/DEMO_SCRIPT_10MIN.md",
]

# exports 中的 secret 检测。
_SECRET = re.compile(r"sk-[A-Za-z0-9]{16,}")


def _check(label: str, status: str, detail: str = "", fix: str = "") -> dict:
    """构造一个检查项记录。"""
    return {"label": label, "status": status, "detail": detail, "fix": fix}


def run_checks(mock: bool, real_check: bool) -> list[dict]:
    """执行全部诊断检查，返回检查项列表。"""
    checks: list[dict] = []

    # 1) Python 版本。
    py_ok = sys.version_info >= (3, 10)
    checks.append(_check("Python >= 3.10", "ok" if py_ok else "error", f"当前 {sys.version.split()[0]}"))

    # 2) 关键依赖。
    for pkg in [
        "pydantic",
        "pydantic_settings",
        "fastapi",
        "streamlit",
        "plotly",
        "networkx",
        "openai",
        "httpx",
        "dashscope",
        "fitz",
        "zvec",
    ]:
        try:
            __import__(pkg)
            checks.append(_check(f"package: {pkg}", "ok"))
        except Exception:
            sev = "warning" if pkg in ("zvec", "fitz") else "error"
            checks.append(_check(f"package: {pkg}", sev, "未安装", "pip install -r requirements.txt"))

    # 3) .env 存在。
    env_path = PROJECT_ROOT / ".env"
    checks.append(_check(".env exists", "ok" if env_path.exists() else "warning",
                         "存在" if env_path.exists() else "缺失", "py -3 scripts/setup_env.py"))

    # 4) 配置（不打印 Key）。
    from app.core.config import get_settings

    s = get_settings()
    checks.append(_check("DASHSCOPE_API_KEY configured", "ok" if s.dashscope_api_key else "warning",
                         "已配置（掩码）" if s.dashscope_api_key else "未配置（Mock 模式无需）", "py -3 scripts/setup_env.py"))
    checks.append(_check("WORKSPACE_ID configured", "ok" if s.workspace_id else "warning",
                         "已配置" if s.workspace_id else "未配置", "py -3 scripts/setup_env.py"))
    placeholder_ok = "你的WorkspaceId" not in (s.dashscope_base_url or "")
    checks.append(_check("DASHSCOPE_BASE_URL placeholder replaced", "ok" if placeholder_ok else "warning",
                         "已替换" if placeholder_ok else "仍含占位符", "py -3 scripts/setup_env.py"))

    # 5) questions_125.json。
    qpath = PROJECT_ROOT / "data" / "processed" / "questions_125.json"
    qcount = 0
    pandemic = False
    if qpath.exists():
        try:
            items = json.loads(qpath.read_text(encoding="utf-8"))
            qcount = len(items)
            pandemic = any("pandemic" in it.get("question", "").lower() for it in items)
        except Exception:
            pass
    checks.append(_check("questions_125.json exists", "ok" if qpath.exists() else "error",
                         f"{qcount} 个", "py -3 scripts/extract_125_questions.py"))
    checks.append(_check("questions count == 125", "ok" if qcount == 125 else "warning", f"{qcount}",
                         "py -3 scripts/extract_125_questions.py"))
    checks.append(_check("pandemic question exists", "ok" if pandemic else "warning",
                         "存在" if pandemic else "未找到"))

    # 6) RAG index。
    zvec_dir = PROJECT_ROOT / "data" / "index" / "zvec"
    rag_ready = zvec_dir.exists() and any(zvec_dir.iterdir()) if zvec_dir.exists() else False
    checks.append(_check("RAG index exists", "ok" if rag_ready else "warning",
                         "就绪" if rag_ready else "未构建", "py -3 scripts/build_rag_index.py --mock-embedding"))
    chunks = PROJECT_ROOT / "data" / "index" / "chunks.jsonl"
    checks.append(_check("chunks.jsonl exists", "ok" if chunks.exists() else "warning",
                         "存在" if chunks.exists() else "缺失"))

    # 7) latest run。
    from app.ui.run_browser import latest_run

    lr = latest_run()
    checks.append(_check("latest run available", "ok" if lr else "warning",
                         (lr or {}).get("run_id", "暂无"), "$env:MOCK_LLM=\"true\"; py -3 scripts/run_demo.py; Remove-Item Env:\\MOCK_LLM"))

    # 8) API import。
    try:
        from app.api.main import app as _app  # noqa: F401

        checks.append(_check("API import works", "ok"))
    except Exception as exc:
        checks.append(_check("API import works", "error", str(exc)[:80]))

    # 9) Streamlit app 文件存在。
    st_app = PROJECT_ROOT / "app" / "ui" / "streamlit_app.py"
    checks.append(_check("Streamlit app present", "ok" if st_app.exists() else "error"))

    # 10) 无参赛材料残留文件。
    residual = [f for f in _FORBIDDEN_FILES if (PROJECT_ROOT / f).exists()]
    checks.append(_check("no submission/demo/technical_solution files", "ok" if not residual else "error",
                         "无残留" if not residual else f"残留：{residual}"))

    # 11) exports 无 sk- 长串。
    leaked = []
    exports = PROJECT_ROOT / "exports"
    if exports.exists():
        for p in exports.rglob("*"):
            if p.is_file() and p.suffix in (".json", ".md", ".txt", ".jsonl", ".html", ".csv"):
                try:
                    if _SECRET.search(p.read_text(encoding="utf-8", errors="ignore")):
                        leaked.append(p.name)
                except OSError:
                    continue
    checks.append(_check("no sk- key in exports", "ok" if not leaked else "error",
                         "无泄露" if not leaked else f"疑似：{leaked[:3]}"))

    # 12) report exporter works（mock plan）。
    try:
        from app.core.schemas import EvidenceCard, ResearchPlan
        from app.exporters.markdown_exporter import render_research_plan_markdown

        ev = EvidenceCard(id="EV-D", source_type="rag", title="t", quoted_text="q", summary="s",
                          relevance_score=0.5, reliability_note="mock_for_testing")
        plan = ResearchPlan(input_question="Q", domain="D", problem_statement="P", rationale="R",
                            datasets={"source": "s", "target": "t"},
                            experiments={"baselines": ["b"], "metrics": ["m"]},
                            results="当前状态：待执行验证实验。", references=[ev], validation_status="ready_for_validation")
        md = render_research_plan_markdown(plan)
        checks.append(_check("report exporter works", "ok" if "## References" in md else "warning"))
    except Exception as exc:
        checks.append(_check("report exporter works", "error", str(exc)[:80]))

    # 13) 真实模式深检（可选）：显式执行一次短时、零重试的 Qwen 探针。
    # 用 execution_mode(False) 避免调用者遗留的 MOCK_LLM 环境变量造成假成功。
    if real_check:
        from app.core.execution_mode import execution_mode
        from app.workflow.preflight import run_real_preflight

        with execution_mode(False):
            result = run_real_preflight(
                settings=s,
                use_local_rag=False,
                use_deep_research=False,
                check_connectivity=True,
            )
        connectivity = result.get("connectivity", {})
        if connectivity.get("ok"):
            checks.append(_check(
                "Qwen connectivity/auth/model probe",
                "ok",
                "百炼 HTTPS、鉴权与快速模型均可用",
            ))
        else:
            details = result.get("errors") or [connectivity.get("error") or "未知失败"]
            fixes = result.get("fix_commands") or ["py -3 scripts/setup_env.py"]
            checks.append(_check(
                "Qwen connectivity/auth/model probe",
                "error",
                "；".join(str(item) for item in details),
                "；".join(str(item) for item in fixes),
            ))
    return checks


def main() -> int:
    """诊断主入口。"""
    parser = argparse.ArgumentParser(description="项目本体诊断")
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--real-check", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    setup_logging("INFO")
    checks = run_checks(args.mock, args.real_check)

    n_error = sum(1 for c in checks if c["status"] == "error")
    n_warn = sum(1 for c in checks if c["status"] == "warning")
    overall = "ERROR" if n_error else ("WARNING" if n_warn else "OK")

    # 写 JSON（可选）。
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report = {"overall": overall, "errors": n_error, "warnings": n_warn, "checks": checks}
    (OUT_DIR / "doctor_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        icon = {"ok": "[OK]  ", "warning": "[WARN]", "error": "[ERR] "}
        print("=" * 70)
        print(f"SAGE125 Doctor · 结果：{overall}（error={n_error}, warning={n_warn}）")
        print("=" * 70)
        for c in checks:
            line = f"{icon.get(c['status'], '[?]')} {c['label']}"
            if c["detail"]:
                line += f" — {c['detail']}"
            print(line)
            if c["status"] != "ok" and c.get("fix"):
                print(f"        fix: {c['fix']}")
        print("=" * 70)
        print(f"报告：{OUT_DIR / 'doctor_report.json'}")
    # critical error 返回 1。
    return 1 if n_error else 0


if __name__ == "__main__":
    sys.exit(main())
