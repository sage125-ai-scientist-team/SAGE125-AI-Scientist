"""
app.workflow.artifacts —— 运行产物（artifacts）管理与保存。

将一次 pipeline 运行的全部产物保存到 exports/{run_id}/，包括报告、证据、
Agent 追踪、上下文包、质量门、状态、错误与警告，以及可读的 run_summary.txt。

安全：不保存 API Key、不保存 .env；使用 pathlib 组织路径。
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.logging import get_logger, mask_text

# 模块级日志器。
logger = get_logger("workflow.artifacts")


def resolve_artifact_base(configured: str | Path = "exports") -> Path:
    """Use an isolated pytest artifact root when configured by conftest."""
    return Path(os.getenv("SAGE_TEST_EXPORT_DIR") or configured)


def generate_run_id() -> str:
    """
    生成运行 ID：YYYYMMDD-HHMMSS-{short_uuid}。

    返回：
        运行 ID 字符串。
    """
    # 时间戳 + 短 uuid，兼顾可读与唯一。
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{ts}-{uuid.uuid4().hex[:8]}"


def _dump(obj: Any) -> Any:
    """将 pydantic 对象/嵌套结构转为可 JSON 序列化的数据。"""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, list):
        return [_dump(x) for x in obj]
    return obj


class ArtifactManager:
    """负责将运行产物写入 exports/{run_id}/。"""

    def __init__(self, run_id: str, base_dir: str = "exports") -> None:
        """
        初始化产物管理器并创建导出目录。

        参数：
            run_id:   运行 ID。
            base_dir: 导出根目录（默认 exports）。
        """
        # 运行导出目录。
        self.run_id = run_id
        self.run_dir = Path(base_dir) / run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)

    def _write_json(self, name: str, data: Any) -> str:
        """写入一个 pretty JSON 文件，返回路径。"""
        path = self.run_dir / name
        path.write_text(json.dumps(_dump(data), ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return str(path)

    def save_started(self, state) -> str:
        """Persist a minimal marker immediately so an interrupted run is diagnosable."""
        return self._write_json(
            "run_status.json",
            {
                "run_id": self.run_id,
                "status": "running",
                "mode": getattr(state, "run_mode", "mock"),
                "question_id": getattr(getattr(state, "selected_question", None), "id", ""),
                "started_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    def save_failure(self, state, error: Exception | str) -> dict[str, str]:
        """Persist partial trace/audit/state when the normal final artifact phase fails."""
        safe_error = mask_text(str(error))
        if safe_error and safe_error not in (getattr(state, "errors", []) or []):
            state.errors.append(safe_error)
        paths = {
            "run_status.json": self._write_json(
                "run_status.json",
                {
                    "run_id": self.run_id,
                    "status": "failed",
                    "mode": getattr(state, "run_mode", "mock"),
                    "question_id": getattr(getattr(state, "selected_question", None), "id", ""),
                    "failed_at": datetime.now(timezone.utc).isoformat(),
                    "error_type": type(error).__name__ if isinstance(error, Exception) else "Error",
                    "error": safe_error,
                },
            ),
            "errors.json": self._write_json("errors.json", getattr(state, "errors", [])),
            "warnings.json": self._write_json("warnings.json", getattr(state, "warnings", [])),
            "agent_trace.json": self._write_json("agent_trace.json", getattr(state, "agent_trace", [])),
            "pipeline_state.json": self._write_json("pipeline_state.json", state),
            "llm_call_audit.json": self._write_llm_call_audit(state),
        }
        logger.info("失败运行状态已保存到 %s", self.run_dir)
        return paths

    def save_all(self, state, plan: Any, quality_gates: dict) -> dict:
        """
        保存全部产物并返回文件路径映射。

        参数：
            state:         PipelineState。
            plan:          最终 ResearchPlan（对象或 dict）。
            quality_gates: 质量门汇总。

        返回：
            {文件名: 路径} 映射。
        """
        paths: dict[str, str] = {}
        paths["run_status.json"] = self._write_json(
            "run_status.json",
            {
                "run_id": self.run_id,
                "status": "completed",
                "mode": getattr(state, "run_mode", "mock"),
                "question_id": getattr(getattr(state, "selected_question", None), "id", ""),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        # 报告 JSON。
        paths["report.json"] = self._write_json("report.json", plan)
        # 证据卡。
        paths["evidence_cards.json"] = self._write_json("evidence_cards.json", state.retrieved_evidence)
        # Agent 追踪。
        paths["agent_trace.json"] = self._write_json("agent_trace.json", state.agent_trace)
        # 上下文包（若已由 context_builder 保存则复用，否则写 state.context_pack）。
        if state.context_pack is not None:
            paths["context_pack.json"] = self._write_json("context_pack.json", state.context_pack)
        # 质量门。
        paths["quality_gates.json"] = self._write_json("quality_gates.json", quality_gates)
        # 流水线状态（完整快照）。
        paths["pipeline_state.json"] = self._write_json("pipeline_state.json", state)
        # LLM 调用审计（脱敏；证明是否真实调用 Qwen）。
        paths["llm_call_audit.json"] = self._write_llm_call_audit(state)
        # 错误与警告。
        paths["errors.json"] = self._write_json("errors.json", state.errors)
        paths["warnings.json"] = self._write_json("warnings.json", state.warnings)
        # Markdown 报告（复用 exporters.markdown_exporter，失败回退内置）。
        paths["report.md"] = self._write_report_md(plan)
        # HTML 与 PDF 报告（尽力生成，失败忽略，不影响主流程）。
        self._write_report_html_pdf(state, plan, paths)
        # 运行摘要。
        paths["run_summary.txt"] = self._write_run_summary(state, plan, paths)
        # artifacts 清单（含 question_id / mode / 文件大小 / 缺失项）。
        paths["artifacts_manifest.json"] = self._write_artifacts_manifest(state, plan)
        logger.info("artifacts 已保存到 %s（%d 个文件）", self.run_dir, len(paths))
        return paths

    def _write_llm_call_audit(self, state) -> str:
        """
        写入 llm_call_audit.json（脱敏调用记录 + 汇总）。

        参数：
            state: PipelineState（含 llm_calls）。

        返回：
            文件路径。
        """
        from app.core.call_audit import summarize_calls

        records = getattr(state, "llm_calls", []) or []
        payload = {
            "run_id": self.run_id,
            "run_mode": getattr(state, "run_mode", "mock"),
            "summary": summarize_calls(records),
            "records": records,
        }
        return self._write_json("llm_call_audit.json", payload)

    def _write_artifacts_manifest(self, state, plan: Any) -> str:
        """
        写入 artifacts_manifest.json（run 元信息 + 各文件是否存在与大小）。

        参数：
            state: PipelineState。
            plan:  最终 ResearchPlan。

        返回：
            文件路径。
        """
        p = _dump(plan)
        # 期望存在的核心 artifact 文件清单。
        expected = [
            "report.json", "report.md", "report.html", "report.pdf",
            "evidence_cards.json", "agent_trace.json", "context_pack.json",
            "quality_gates.json", "run_summary.txt", "llm_call_audit.json",
        ]
        files = []
        missing = []
        for name in expected:
            fp = self.run_dir / name
            exists = fp.exists()
            files.append({"name": name, "exists": exists, "size": fp.stat().st_size if exists else 0})
            if not exists:
                missing.append(name)
        qi = state.selected_question
        question_id = qi.id if hasattr(qi, "id") else qi.get("id")
        manifest = {
            "run_id": self.run_id,
            "question_id": question_id or p.get("question_id", ""),
            "mode": getattr(state, "run_mode", "mock"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "files": files,
            "missing_files": missing,
            "warnings": list(getattr(state, "warnings", []) or []),
        }
        return self._write_json("artifacts_manifest.json", manifest)

    def _write_report_html_pdf(self, state, plan: Any, paths: dict) -> None:
        """
        生成 report.html 与 report.pdf（尽力而为，失败仅记日志，不中断）。

        说明：这是**当前运行结果**的 ResearchPlan 报告导出，不限制页数、
        不作为参赛技术方案 PDF。
        """
        # HTML。
        try:
            from app.exporters.html_exporter import export_research_plan_html

            export_research_plan_html(plan, state.retrieved_evidence, state.agent_trace,
                                      self.run_dir / "report.html", run_id=self.run_id)
            paths["report.html"] = str(self.run_dir / "report.html")
        except Exception as exc:
            logger.warning("report.html 生成失败（忽略）：%s", exc)
        # PDF（由 report.md 生成；WeasyPrint 优先，ReportLab 兜底）。
        try:
            from app.exporters.pdf_exporter import export_markdown_to_pdf

            md_path = self.run_dir / "report.md"
            if md_path.exists():
                result = export_markdown_to_pdf(md_path, self.run_dir / "report.pdf")
                if result.get("status") == "ok":
                    paths["report.pdf"] = str(self.run_dir / "report.pdf")
        except Exception as exc:
            logger.warning("report.pdf 生成失败（忽略）：%s", exc)

    def _write_report_md(self, plan: Any) -> str:
        """生成 report.md（优先复用 markdown_exporter，失败则内置简易生成）。"""
        p = _dump(plan)
        path = self.run_dir / "report.md"
        # 优先复用正式的 ResearchPlan Markdown 导出器。
        try:
            from app.exporters.markdown_exporter import render_research_plan_markdown

            path.write_text(render_research_plan_markdown(plan), encoding="utf-8")
            return str(path)
        except Exception:
            # 内置简易 Markdown 生成。
            lines = [
                f"# {p.get('paper_title') or p.get('input_question', '研究计划')}",
                "",
                f"- 领域：{p.get('domain')}",
                f"- 校验状态：{p.get('validation_status')}",
                "",
                "## 问题陈述",
                p.get("problem_statement", ""),
                "",
                "## 摘要",
                p.get("paper_abstract", ""),
                "",
                "## 方法",
                p.get("methods", ""),
                "",
                "## 结果",
                p.get("results", ""),
                "",
                "## 参考证据",
            ]
            for ref in p.get("references", []):
                r = _dump(ref)
                lines.append(f"- [{r.get('id')}] {r.get('title')}")
            path.write_text("\n".join(str(x) for x in lines) + "\n", encoding="utf-8")
        return str(path)

    def _write_run_summary(self, state, plan: Any, paths: dict) -> str:
        """生成 run_summary.txt。"""
        p = _dump(plan)
        qi = state.selected_question
        question = qi.question if hasattr(qi, "question") else qi.get("question")
        domain = qi.domain if hasattr(qi, "domain") else qi.get("domain")
        # 统计已完成 agent。
        completed = [ev.get("agent_name") for ev in state.agent_trace if ev.get("status") == "completed"]
        lines = [
            f"run_id: {self.run_id}",
            f"selected_question: {question}",
            f"domain: {domain}",
            f"validation_status: {p.get('validation_status')}",
            f"evidence_count: {len(state.retrieved_evidence)}",
            f"agents_completed: {', '.join(completed)}",
            f"export_files: {', '.join(paths.keys())}",
            "pending_results_note: 无真实实验时 Results 为 pending；mock 结果不可作为真实科学结论。",
        ]
        path = self.run_dir / "run_summary.txt"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return str(path)
