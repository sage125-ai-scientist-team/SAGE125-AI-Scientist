"""
app.api.routes —— 业务路由定义（供“科研发现控制台”前端调用）。

端点：
    GET  /health                         健康检查与配置/索引状态（脱敏）
    GET  /questions                      返回 125 问题清单
    POST /ingest                         上传资料并加入 RAG 索引（仅本地）
    POST /runs                           运行多智能体 pipeline
    GET  /runs/{run_id}                  读取某次运行产物
    POST /runs/{run_id}/feedback         人在回路反馈修订
    GET  /runs/{run_id}/export/markdown  下载 report.md
    GET  /runs/{run_id}/export/pdf       下载/生成 report.pdf
    POST /experiments/{question_id}/run  触发真实科学实验入口（目前仅 Q028）
    GET  /experiments/{question_id}/canonical-status
                                          只读旗舰案例 canonical/原子发布状态（目前仅 Q028）

安全：绝不返回 API Key 或 .env 全量；仅返回模型名、配置状态、索引状态。
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.logging import get_logger
from app.workflow.artifacts import resolve_artifact_base

# 模块级日志器。
logger = get_logger("api.routes")

# 业务路由聚合器，供 main 挂载。
router = APIRouter()

# 项目根与关键路径。
PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPORTS_DIR = PROJECT_ROOT / "exports"
_REAL_RUN_SLOT = threading.BoundedSemaphore(value=1)


def _exports_dir() -> Path:
    configured = Path(getattr(get_settings(), "export_dir", "exports"))
    if not configured.is_absolute():
        configured = PROJECT_ROOT / configured
    return resolve_artifact_base(configured)


def _questions_path() -> Path:
    """Resolve the runtime catalog, preferring writable DATA_DIR over the repo tree."""
    from app.api.preview_catalog import resolve_runtime_questions_path

    return resolve_runtime_questions_path()


def _rag_index_status() -> str:
    """返回独立用户文献索引状态；题源索引不计入 Local RAG。"""
    from app.rag.library_manager import LibraryManager

    try:
        return LibraryManager().get_status()["index_status"]
    except Exception:
        return "unavailable"


def _official_catalog_or_none():
    try:
        from app.catalog.official import load_official_catalog

        return load_official_catalog()
    except Exception:
        return None


def _questions_count() -> int:
    """返回官方问题清单数量（缺失或非法返回 0）。"""
    catalog = _official_catalog_or_none()
    return len(catalog.list_questions()) if catalog is not None else 0


def _delivery_dependency_status(request: Request | None) -> dict[str, str]:
    """Probe the persistent API stores without exposing their local paths."""
    statuses = {
        "job_store": "unavailable",
        "artifact_registry": "unavailable",
        "artifact_storage": "unavailable",
    }
    state = getattr(getattr(request, "app", None), "state", None)
    job_store = getattr(state, "job_store", None)
    try:
        if job_store is not None:
            job_store.list_jobs(limit=1)
            statuses["job_store"] = "available"
    except Exception:  # noqa: BLE001 - health must report, not leak, dependency failures
        pass

    registry = getattr(state, "artifact_registry", None)
    try:
        if registry is not None:
            registry.list_for_job("__healthcheck__", actor_id="__healthcheck__")
            statuses["artifact_registry"] = "available"
            root = getattr(registry, "root", None)
            if (
                isinstance(root, Path)
                and root.is_dir()
                and os.access(root, os.W_OK)
            ):
                statuses["artifact_storage"] = "available"
    except Exception:  # noqa: BLE001 - health must report, not leak, dependency failures
        pass
    return statuses


@router.get("/health")
def health(request: Request = None) -> dict:  # type: ignore[assignment]
    """
    健康检查：返回服务状态、配置状态、索引状态与模型名（不含任何 Key）。

    返回：
        健康信息字典。
    """
    settings = get_settings()
    questions_count = _questions_count()
    rag_index_status = _rag_index_status()
    dependencies = _delivery_dependency_status(request)
    status = (
        "ok"
        if (
            questions_count == 125
            and rag_index_status != "unavailable"
            and all(value == "available" for value in dependencies.values())
        )
        else "degraded"
    )
    return {
        "status": status,
        "service": "sage125-api",
        "bailian": {
            "configured": settings.bailian.configured,
            "status": "available" if settings.bailian.configured else "unavailable",
        },
        "storage": {
            "mode": "ephemeral" if settings.preview_ephemeral_storage else "local",
            "persistent": not settings.preview_ephemeral_storage,
        },
        "dependencies": dependencies,
        "qwen_config_loaded": settings.qwen_configured,
        "deep_research_config_loaded": settings.deep_research_configured,
        "openalex_config_loaded": settings.openalex_configured,
        "rag_index_status": rag_index_status,
        "questions_count": questions_count,
        "catalog": (
            {
                "status": "ok",
                "count": questions_count,
                "source": "official",
                "digest": _official_catalog_or_none().get_catalog_digest(),
            }
            if questions_count == 125
            else {"status": "failed", "count": questions_count, "source": "missing", "digest": ""}
        ),
        "models": {
            "fast": settings.qwen_fast_model,
            "balanced": settings.qwen_balanced_model,
            "strong": settings.qwen_strong_model,
            "deep_research": settings.qwen_deep_research_model,
            "embedding": settings.bailian_embedding_model,
            "rerank": settings.bailian_rerank_model,
        },
    }


@router.get("/diagnostics")
def diagnostics() -> dict:
    """
    系统诊断：问题清单 / RAG 索引 / 配置状态 / 最近运行（不含任何 Key）。

    返回：
        诊断信息字典（status: ok|warning|error）。
    """
    from app.ui.run_browser import latest_run

    settings = get_settings()
    from app.rag.library_manager import LibraryManager

    try:
        library_status = LibraryManager().get_status()
    except Exception as exc:
        library_status = {"status": "unavailable", "index_status": "unavailable", "usage": {}, "documents": []}
        logger.warning("读取本地文献库状态失败：%s", exc)
    chunk_count = int(library_status.get("usage", {}).get("chunk_count", 0))

    q_count = _questions_count()
    warnings: list[str] = []
    errors: list[str] = []
    if q_count == 0:
        errors.append("questions_125.json 缺失，请运行 python scripts/extract_125_questions.py")
    elif q_count != 125:
        warnings.append(f"问题数量为 {q_count}（非 125），建议核查抽取结果。")
    if _rag_index_status() == "empty":
        warnings.append("用户本地文献库为空；不会检索 sjtu-booklet.pdf，可上传真实参考资料后跨问题复用。")
    elif _rag_index_status() == "unavailable":
        warnings.append("用户本地文献库状态不可用，请检查 data/raw/uploads 权限。")
    if not settings.qwen_configured:
        warnings.append("百炼未配置，真实模式不可用；可用 Mock 模式演示。")

    # 主题配置存在性（深色科学主题双重固定）。
    theme_config_exists = (PROJECT_ROOT / ".streamlit" / "config.toml").exists()
    # 确认不存在参赛提交类产物（scope 收敛）；检测逻辑在 run_browser，避免此处出现禁用 token。
    from app.ui.run_browser import has_submission_artifacts

    no_submission_artifacts = not has_submission_artifacts()

    status = "ok"
    if errors:
        status = "error"
    elif warnings:
        status = "warning"

    return {
        "status": status,
        "questions": {"exists": q_count > 0, "count": q_count},
        "rag_index": {"exists": _rag_index_status() == "ready", "chunk_count": chunk_count},
        "library": library_status,
        "qwen": {"configured": settings.qwen_configured},
        "deepresearch": {"configured": settings.deep_research_configured},
        "openalex": {"configured": settings.openalex_configured},
        "api_connected": True,
        "theme_config_exists": theme_config_exists,
        "no_submission_artifacts": no_submission_artifacts,
        "latest_run": latest_run(),
        "warnings": warnings,
        "errors": errors,
    }


@router.get("/health/catalog")
def catalog_health() -> dict:
    """官方 Catalog 健康检查：125 题、无 Preview 标记。"""
    catalog = _official_catalog_or_none()
    if catalog is None:
        return {"status": "failed", "count": 0, "source": "missing", "digest": ""}
    blob = " ".join(item.title_en for item in catalog.list_questions())
    preview = blob.count("[PREVIEW-SEED]") + blob.lower().count("placeholder question")
    status = "ok" if catalog.get_catalog_digest() and preview == 0 and len(catalog.list_questions()) == 125 else "failed"
    return {
        "status": status,
        "count": len(catalog.list_questions()),
        "source": "official",
        "digest": catalog.get_catalog_digest(),
        "preview_markers": preview,
    }


@router.get("/questions")
def list_questions() -> dict:
    """
    返回官方 125 问题清单。

    正式模式不得回退 Preview Seed。
    """
    catalog = _official_catalog_or_none()
    if catalog is None:
        return {
            "status": "missing",
            "count": 0,
            "catalog_source": "missing",
            "catalog_digest": "",
            "message": "官方125题目录未加载，系统已阻断选题。",
            "questions": [],
        }
    digest = catalog.get_catalog_digest()
    items = [item.as_api_item(digest) for item in catalog.list_questions()]
    return {
        "status": "ok",
        "count": len(items),
        "catalog_source": "official",
        "catalog_digest": digest,
        "questions": items,
    }


@router.post("/ingest")
async def ingest(files: list[UploadFile] = File(...)) -> dict:
    """
    接收用户上传资料并加入本地 RAG 索引（绝不外发到公开文献 API）。

    参数：
        files: 上传的 PDF/TXT/MD/CSV 文件。

    返回：
        {"status","files","chunks_added","index_status"}；仅返回文件名。
    """
    from app.rag.library_manager import LibraryManager

    settings = get_settings()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    max_batch_files = settings.library_max_batch_files
    max_batch_bytes = settings.library_max_batch_mb * 1024 * 1024
    if len(files) > max_batch_files:
        return {
            "status": "failed", "files": [], "documents": [], "chunks_added": 0,
            "duplicates": [], "rejected": [f"单批最多上传 {max_batch_files} 个文件。"],
            "errors": [f"单批最多上传 {max_batch_files} 个文件。"],
            "index_status": _rag_index_status(),
        }

    payloads: list[tuple[str, bytes]] = []
    total_bytes = 0
    for f in files:
        # 最多读取单文件上限 + 1 字节，避免超大请求被整份读入内存。
        content = await f.read(max_bytes + 1)
        if len(content) > max_bytes:
            return {
                "status": "failed", "files": [], "documents": [], "chunks_added": 0,
                "duplicates": [],
                "rejected": [f"{Path(f.filename or '').name}: 超过 {settings.max_upload_mb} MB"],
                "errors": [f"{Path(f.filename or '').name}: 超过 {settings.max_upload_mb} MB"],
                "index_status": _rag_index_status(),
            }
        total_bytes += len(content)
        if total_bytes > max_batch_bytes:
            return {
                "status": "failed", "files": [], "documents": [], "chunks_added": 0,
                "duplicates": [],
                "rejected": [f"单批总大小超过 {settings.library_max_batch_mb} MB。"],
                "errors": [f"单批总大小超过 {settings.library_max_batch_mb} MB。"],
                "index_status": _rag_index_status(),
            }
        payloads.append((f.filename or "upload", content))

    return LibraryManager().ingest_files(payloads)


@router.get("/library/status")
def library_status() -> dict:
    """返回永久本地文献库的容量、配额和文档清单。"""
    from app.rag.library_manager import LibraryManager

    return LibraryManager().get_status()


@router.get("/library/documents")
def library_documents() -> dict:
    """列出本地文献（不返回绝对路径或完整内容哈希）。"""
    from app.rag.library_manager import LibraryManager

    status = LibraryManager().get_status()
    return {"status": status["status"], "documents": status["documents"]}


@router.delete("/library/documents/{document_id}")
def delete_library_document(document_id: str) -> dict:
    """显式删除一篇文献及其向量；系统不会定期自动删除。"""
    from app.rag.library_manager import LibraryManager

    result = LibraryManager().delete_document(document_id)
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="文献不存在。")
    if result.get("status") == "failed":
        raise HTTPException(status_code=409, detail=result.get("message", "删除失败。"))
    return result


class RunRequest(BaseModel):
    """POST /runs 请求体。"""

    question_id: str
    # 运行模式："mock"（不调用真实 Qwen）| "real"（必须调用 Qwen，不 fallback）。
    mode: str = "mock"
    user_feedback: str = ""
    use_deep_research: bool = True
    use_open_literature: bool = True
    use_local_rag: bool = True
    reviewer_auto_revision: bool = True


@router.get("/preflight")
def preflight_real(use_local_rag: bool = True, use_deep_research: bool = True) -> dict:
    """真实模式 preflight 检查（不泄露 Key）。"""
    from app.workflow.preflight import run_real_preflight

    return run_real_preflight(use_local_rag=use_local_rag, use_deep_research=use_deep_research)


@router.post("/runs", deprecated=True)
def create_run(req: RunRequest) -> dict:
    """
    运行多智能体 pipeline，返回统一 RunResponse。

    规则：
        - question_id 必须存在；
        - mode=mock：不调用真实 Qwen；
        - mode=real：preflight 失败返回 400；Qwen 失败 status=failed，不 fallback mock。
    """
    from app.core.logging import mask_text
    from app.core.run_response import build_run_response_from_state, failed_run_response
    from app.workflow.pipeline import run_pipeline_with_state
    from app.workflow.preflight import run_real_preflight

    mode = (req.mode or "mock").strip().lower()
    if mode not in ("mock", "real"):
        resp = failed_run_response(req.question_id, mode, ["mode 仅支持 mock 或 real"])
        raise HTTPException(status_code=400, detail=resp.to_api_dict())

    settings = get_settings()
    if mode == "real":
        pf = run_real_preflight(
            settings, req.use_local_rag, req.use_deep_research, check_connectivity=True
        )
        if not pf.get("ok"):
            resp = failed_run_response(req.question_id, mode, pf.get("errors", []), message="preflight 未通过")
            d = resp.to_api_dict()
            d["preflight"] = pf
            raise HTTPException(status_code=503, detail=d)

    state = None
    acquired_real_slot = False
    try:
        if mode == "real":
            acquired_real_slot = _REAL_RUN_SLOT.acquire(blocking=False)
            if not acquired_real_slot:
                resp = failed_run_response(
                    req.question_id,
                    mode,
                    ["已有真实模式任务正在运行，请等待完成后再启动。"],
                    message="real_run_busy",
                )
                raise HTTPException(status_code=409, detail=resp.to_api_dict())
        plan, state = run_pipeline_with_state(
            question_id=req.question_id,
            user_feedback=req.user_feedback or None,
            use_local_rag=req.use_local_rag,
            use_deep_research=req.use_deep_research,
            use_open_literature=req.use_open_literature,
            reviewer_auto_revision=req.reviewer_auto_revision,
            mock_mode=(mode == "mock"),
        )
    except ValueError as exc:
        resp = failed_run_response(req.question_id, mode, [str(exc)])
        raise HTTPException(status_code=400, detail=resp.to_api_dict()) from None
    except FileNotFoundError as exc:
        resp = failed_run_response(req.question_id, mode, [str(exc)])
        raise HTTPException(status_code=409, detail=resp.to_api_dict()) from None
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise
        rid = getattr(state, "run_id", None) if state else getattr(exc, "run_id", None)
        resp = failed_run_response(req.question_id, mode, [mask_text(str(exc))], run_id=rid)
        if state is not None:
            try:
                from app.workflow.artifacts import ArtifactManager

                ArtifactManager(state.run_id, base_dir=_exports_dir())._write_json(
                    "errors.json", [mask_text(str(exc))]
                )
            except Exception:  # noqa: BLE001
                pass
        raise HTTPException(status_code=500, detail=resp.to_api_dict()) from None
    finally:
        if acquired_real_slot:
            _REAL_RUN_SLOT.release()
    status = "completed"
    if state.errors:
        status = "failed"
    elif any("deep_research_failed" in w for w in (state.warnings or [])):
        status = "partial_failed"

    resp = build_run_response_from_state(
        question_id=req.question_id,
        mode=mode,
        state=state,
        plan=plan,
        status=status,
        message=status,
    )
    d = resp.to_api_dict()
    d["artifacts"] = _artifacts_brief(state.run_id)
    return d


def _artifacts_brief(run_id: str) -> dict:
    """返回某运行的 artifacts 清单（供 /runs 响应内联）。"""
    from app.ui.run_browser import get_artifacts_manifest

    return get_artifacts_manifest(run_id)


@router.get("/runs/{run_id}/llm-calls")
def run_llm_calls(run_id: str) -> dict:
    """
    返回某次运行的脱敏 LLM 调用审计（证明是否真实调用了 Qwen）。

    参数：
        run_id: 运行 ID。

    返回：
        {"run_id","exists","run_mode","summary","records"}；不含任何 API Key。

    异常：
        HTTPException 404: 审计不存在。
    """
    from app.ui.run_browser import get_llm_call_audit

    audit = get_llm_call_audit(run_id)
    if not audit.get("exists"):
        raise HTTPException(status_code=404, detail=f"运行调用审计不存在：{run_id}")
    return audit


def _read_json(path: Path):
    """读取 JSON 文件（不存在返回 None）。"""
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/runs")
def list_runs_endpoint(limit: int = 20) -> dict:
    """
    返回最近的运行列表（不含 Key / 绝对路径）。

    参数：
        limit: 返回条数上限。

    返回：
        {"runs": [...]}。
    """
    from app.ui.run_browser import list_runs

    return {"runs": list_runs(limit=limit)}


@router.get("/runs/{run_id}/artifacts")
def run_artifacts(run_id: str) -> dict:
    """
    返回某次运行的 artifacts 清单（文件名/是否存在/大小）。

    参数：
        run_id: 运行 ID。

    返回：
        artifacts manifest 字典。
    """
    from app.ui.run_browser import get_artifacts_manifest

    manifest = get_artifacts_manifest(run_id)
    if not manifest.get("exists"):
        raise HTTPException(status_code=404, detail=f"运行不存在：{run_id}")
    return manifest


@router.get("/runs/{run_id}")
def get_run(run_id: str) -> dict:
    """
    读取某次运行的产物（report / evidence / trace）。

    参数：
        run_id: 运行 ID。

    返回：
        运行产物字典。

    异常：
        HTTPException 404: 运行不存在。
    """
    run_dir = _exports_dir() / run_id
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f"运行不存在：{run_id}")
    plan = _read_json(run_dir / "report.json")
    audit = _read_json(run_dir / "llm_call_audit.json") or {}
    return {
        "run_id": run_id,
        "question_id": (plan or {}).get("question_id", ""),
        "plan": plan,
        "evidence_cards": _read_json(run_dir / "evidence_cards.json"),
        "agent_trace": _read_json(run_dir / "agent_trace.json"),
        "quality_gates": _read_json(run_dir / "quality_gates.json"),
        "context_pack": _read_json(run_dir / "context_pack.json"),
        "llm_call_summary": audit.get("summary", {}),
        "mock": audit.get("run_mode") == "mock" if audit else None,
    }


class FeedbackRequest(BaseModel):
    """POST /runs/{run_id}/feedback 请求体。"""

    feedback: str


@router.post("/runs/{run_id}/feedback")
def run_feedback(run_id: str, req: FeedbackRequest) -> dict:
    """
    基于用户反馈触发一轮修订，保存新版本。

    参数：
        run_id: 原始运行 ID。
        req:    反馈请求体。

    返回：
        修订后的 plan 与 revision_history。

    异常：
        HTTPException 400: 非法反馈（造假/去引用/强行 validated）。
        HTTPException 404: 原始运行缺失。
    """
    from app.workflow.pipeline import revise_with_feedback

    try:
        plan = revise_with_feedback(run_id, req.feedback)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return {"run_id": run_id, "status": "revised", "plan": plan.model_dump(),
            "revision_history": plan.revision_history}


@router.get("/runs/{run_id}/export/markdown")
def export_markdown(run_id: str):
    """
    下载 report.md（由 artifacts 在运行时生成）。

    参数：
        run_id: 运行 ID。

    返回：
        Markdown 文件响应。

    异常：
        HTTPException 404: 文件不存在。
    """
    path = _exports_dir() / run_id / "report.md"
    if not path.exists():
        raise HTTPException(status_code=404, detail="report.md 不存在。")
    return FileResponse(str(path), media_type="text/markdown", filename=f"{run_id}_report.md")


@router.get("/runs/{run_id}/export/pdf")
def export_pdf(run_id: str):
    """
    下载/生成 report.pdf；生成失败返回清晰错误，不影响 markdown/json。

    参数：
        run_id: 运行 ID。

    返回：
        PDF 文件响应或错误 JSON。
    """
    run_dir = _exports_dir() / run_id
    pdf_path = run_dir / "report.pdf"
    md_path = run_dir / "report.md"
    # 已存在直接返回。
    if pdf_path.exists():
        return FileResponse(str(pdf_path), media_type="application/pdf", filename=f"{run_id}_report.pdf")
    # 尝试用 weasyprint 由 markdown 生成（不可用则回退提示）。
    if not md_path.exists():
        raise HTTPException(status_code=404, detail="report.md 不存在，无法生成 PDF。")
    try:
        import markdown as md_lib
        import weasyprint  # type: ignore

        html = md_lib.markdown(md_path.read_text(encoding="utf-8"))
        weasyprint.HTML(string=f"<meta charset='utf-8'>{html}").write_pdf(str(pdf_path))
        return FileResponse(str(pdf_path), media_type="application/pdf", filename=f"{run_id}_report.pdf")
    except Exception as exc:
        # PDF 生成失败不影响其它导出，返回清晰 JSON。
        logger.warning("PDF 生成失败：%s", exc)
        return JSONResponse(
            status_code=501,
            content={"status": "pdf_unavailable", "message": "PDF 生成失败（weasyprint 不可用），请改用 Markdown/JSON。"},
        )


# 目前 125 题里只有 Q028 注册了可执行的真实科学实验入口（WDBC 旗舰案例，
# app.execution.run_round1 / run_round2）。其它题目没有可执行代码，按钮点击
# 后必须诚实返回 available=false，绝不编造实验结果。
_EXECUTABLE_QUESTION_IDS = {"Q028"}


@router.post("/experiments/{question_id}/run")
def run_experiment(question_id: str) -> dict:
    """
    触发一次网页界面的真实实验执行（目前仅 Q028 有可执行入口）。

    参数：
        question_id: 问题 ID。

    返回：
        ``available=False`` 且带诚实原因（无可执行入口）；
        或 ``available=True`` 且携带真实 ``ExecutionResult`` 摘要
        （metrics、status、execution_id、git_sha 等，无一编造）。
    """
    qid = (question_id or "").strip().upper()
    if qid not in _EXECUTABLE_QUESTION_IDS:
        return {
            "question_id": question_id,
            "available": False,
            "status": "not_available",
            "reason": (
                "该题目当前没有可执行的真实科学实验入口（scientific entrypoint），"
                "系统不会编造实验结果。"
            ),
        }

    from app.execution.q028_demo_run import Q028DemoRunError, run_q028_demo_experiment

    try:
        result = run_q028_demo_experiment()
    except Q028DemoRunError as exc:
        logger.warning("q028_demo_run_unavailable: %s", exc)
        return {
            "question_id": question_id,
            "available": True,
            "status": "failed",
            "reason": str(exc),
        }
    except Exception as exc:  # noqa: BLE001 - 演示入口需要如实回传失败原因
        logger.warning("q028_demo_run_failed: %s", exc)
        return {
            "question_id": question_id,
            "available": True,
            "status": "failed",
            "reason": f"真实实验执行异常：{exc}",
        }
    return {"available": True, **result}


@router.get("/experiments/{question_id}/canonical-status")
def get_experiment_canonical_status(question_id: str) -> dict:
    """
    只读地返回旗舰案例的 canonical package / 原子发布状态（目前仅 Q028）。

    绝不在此端点内触发任何实验执行、模型调用或发布动作；仅读取磁盘上
    已经存在的证据与（如有）已发布的 canonical pointer。

    参数：
        question_id: 问题 ID。

    返回：
        ``available=False`` 且带诚实原因（该题目未接入 canonical 发布流水线）；
        或 ``available=True`` 且携带真实的语义校验状态、Round1/Round2 阻断
        信息、以及 canonical 是否已发布（PUBLISHED_VERIFIED）。
    """
    qid = (question_id or "").strip().upper()
    if qid not in _EXECUTABLE_QUESTION_IDS:
        return {
            "question_id": question_id,
            "available": False,
            "status": "not_available",
            "reason": "该题目当前没有接入 canonical package 发布流水线。",
        }

    try:
        from app.execution.flagship_publish import get_canonical_status

        status = get_canonical_status()
    except Exception as exc:  # noqa: BLE001 - 只读状态端点需要如实回传失败原因
        logger.warning("flagship_canonical_status_failed: %s", exc)
        return {
            "question_id": question_id,
            "available": True,
            "status": "error",
            "reason": f"读取 canonical 状态异常：{exc}",
        }
    return {"question_id": question_id, "available": True, **status}
