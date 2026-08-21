"""
app.ui.api_client —— 前端与本地 FastAPI 的通信 helper。

策略：优先通过 HTTP 调用本地 FastAPI（默认 http://localhost:8000，可用
FRONTEND_API_BASE_URL 覆盖）；当 API 不可达时，自动回退到**进程内**直接调用
pipeline / 读取产物，保证仅运行 `streamlit run` 也能完成 mock 演示。

安全：绝不在请求中携带 API Key；前端只与本地服务/本地进程交互。
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import quote

import requests

from app.workflow.artifacts import resolve_artifact_base

# 项目根与产物目录。
PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPORTS_DIR = PROJECT_ROOT / "exports"
QUESTIONS_PATH = PROJECT_ROOT / "data" / "processed" / "questions_125.json"

# 请求超时（秒）：普通短请求、Render 冷启动探测、上传和长运行分开配置。
# Render Free API 唤醒可能明显超过本地短请求时延，因此不能用 3 秒健康探测
# 作为上传前置门禁。


def _positive_env_int(name: str, default: int) -> int:
    """读取正整数环境变量；非法值安全回退，避免前端导入失败。"""
    try:
        return max(int(os.getenv(name, str(default)) or default), 1)
    except (TypeError, ValueError):
        return default


def _short_timeout_seconds() -> int:
    """普通 API 查询的超时；本地默认保持紧凑，部署时可显式覆盖。"""
    return _positive_env_int("FRONTEND_API_SHORT_TIMEOUT_SECONDS", 10)


def _wake_timeout_seconds() -> int:
    """允许托管 API 从休眠中唤醒的健康探测超时。"""
    return max(_positive_env_int("FRONTEND_API_WAKE_TIMEOUT_SECONDS", 75), 10)


def _ingest_timeout_seconds() -> int:
    """PDF 解析、远程嵌入和索引构建的 HTTP 读超时。"""
    return max(_positive_env_int("FRONTEND_INGEST_TIMEOUT_SECONDS", 900), 60)


# 上传批次的前端早期保护。LibraryManager 返回更严格的配额时，
# validate_upload_batch() 会优先使用服务端配额。
_SUPPORTED_LIBRARY_EXTENSIONS = {".pdf", ".txt", ".md", ".csv"}
_DEFAULT_UPLOAD_MAX_FILES = _positive_env_int("MAX_UPLOAD_FILES", 10)
_DEFAULT_UPLOAD_MAX_MB = _positive_env_int("MAX_UPLOAD_MB", 25)
_DEFAULT_UPLOAD_TOTAL_MB = _positive_env_int(
    "MAX_UPLOAD_TOTAL_MB", _DEFAULT_UPLOAD_MAX_FILES * _DEFAULT_UPLOAD_MAX_MB
)


def _exports_dir() -> Path:
    return resolve_artifact_base(EXPORTS_DIR)


def _run_timeout_seconds(mode: str = "mock", use_deep_research: bool = False) -> int:
    """
    返回 POST /runs 的 HTTP 读超时（秒）。

    Mock 默认 120s；Real 默认 900s；启用 DeepResearch 时至少 1200s。
    可通过 FRONTEND_RUN_TIMEOUT_SECONDS 覆盖。
    """
    override = os.getenv("FRONTEND_RUN_TIMEOUT_SECONDS", "").strip()
    if override.isdigit():
        return max(int(override), 60)
    if mode == "real":
        return 1200 if use_deep_research else 900
    return 120


def _prefer_inprocess_run() -> bool:
    """
    是否优先在 Streamlit 进程内直接跑 pipeline（默认 True，避免 HTTP 读超时）。

    仅当 FRONTEND_RUN_VIA_API=1 时才走 HTTP POST /runs（供 API 集成测试）。
    """
    return os.getenv("FRONTEND_RUN_VIA_API", "").strip().lower() not in ("1", "true", "yes")


def _api_only() -> bool:
    """Whether this UI is explicitly isolated from all in-process backend work."""
    return not _prefer_inprocess_run()


def api_base() -> str:
    """返回 API 基础 URL（可由 FRONTEND_API_BASE_URL 覆盖）。"""
    return os.getenv("FRONTEND_API_BASE_URL", "http://localhost:8000").rstrip("/")


def api_available() -> bool:
    """探测 API 是否可达，并为托管环境冷启动预留时间。"""
    try:
        r = requests.get(f"{api_base()}/health", timeout=_wake_timeout_seconds())
        return r.status_code == 200
    except requests.RequestException:
        return False


# ---- 各接口：HTTP 优先，失败回退进程内 ----

def get_health() -> dict:
    """获取健康状态（HTTP 优先，首次加载允许托管 API 唤醒）。"""
    try:
        r = requests.get(f"{api_base()}/health", timeout=_wake_timeout_seconds())
        if r.status_code == 200:
            return r.json()
    except requests.RequestException:
        pass
    if _api_only():
        return {
            "status": "unavailable",
            "service": "sage125-api",
            "bailian": {"configured": False, "status": "unavailable"},
            "storage": {"mode": "unavailable", "persistent": False},
            "qwen_config_loaded": False,
            "deep_research_config_loaded": False,
            "openalex_config_loaded": False,
            "rag_index_status": "unavailable",
            "questions_count": 0,
            "models": {},
        }
    # 回退：进程内直接读取 settings。
    from app.api.routes import health as _health

    return _health()


def get_diagnostics() -> dict:
    """获取系统诊断（HTTP 优先，回退进程内）。"""
    try:
        r = requests.get(f"{api_base()}/diagnostics", timeout=_short_timeout_seconds())
        if r.status_code == 200:
            return r.json()
    except requests.RequestException:
        pass
    if _api_only():
        return {
            "status": "error",
            "api_connected": False,
            "qwen": {"configured": False},
            "deepresearch": {"configured": False},
            "openalex": {"configured": False},
            "warnings": [],
            "errors": ["sage125-api 暂不可用。"],
        }
    # 回退：进程内调用诊断逻辑。
    from app.api.routes import diagnostics as _diag

    return _diag()


def get_runs(limit: int = 20) -> list[dict]:
    """获取最近运行列表（HTTP 优先，回退进程内 run_browser）。"""
    try:
        r = requests.get(
            f"{api_base()}/runs",
            params={"limit": limit},
            timeout=_short_timeout_seconds(),
        )
        if r.status_code == 200:
            return r.json().get("runs", [])
    except requests.RequestException:
        pass
    if _api_only():
        return []
    from app.ui.run_browser import list_runs

    return list_runs(limit=limit)


def get_questions() -> dict:
    """获取 125 问题清单（HTTP 优先，回退读取本地文件）。"""
    try:
        r = requests.get(f"{api_base()}/questions", timeout=_short_timeout_seconds())
        if r.status_code == 200:
            return r.json()
    except requests.RequestException:
        pass
    if _api_only():
        return {"status": "unavailable", "message": "sage125-api 暂不可用。"}
    # 回退：直接读文件。
    if not QUESTIONS_PATH.exists():
        return {"status": "missing", "message": "请先运行 python scripts/extract_125_questions.py"}
    items = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    return {"status": "ok", "count": len(items), "questions": items}


def _as_dict(value: Any) -> dict:
    """将 LibraryManager/API 返回值安全转成 dict。"""
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "model_dump"):
        dumped = value.model_dump()
        return dict(dumped) if isinstance(dumped, dict) else {}
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    return {}


# UI 的最后一道脱敏防线：兼容第三方 SDK 常见的 Header、Bearer 与 URL
# 查询参数格式。嵌入错误会先被归类成固定中文指引；这些表达式只用于无法
# 归类的本地文献库错误，避免把认证信息原样展示给用户。
_BEARER_SECRET_PATTERN = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{6,}", re.IGNORECASE)
_NAMED_SECRET_PATTERN = re.compile(
    r"\b(api[_ -]?key|authorization|access[_ -]?token|token|secret|password)"
    r"(\s*[:=]\s*)(?:Bearer\s+)?[^\s,;\]}\)]+",
    re.IGNORECASE,
)
_QUERY_SECRET_PATTERN = re.compile(
    r"([?&](?:api[_-]?key|access[_-]?token|token|secret|signature)=)[^&#\s]+",
    re.IGNORECASE,
)


def _safe_library_error_text(value: Any) -> str:
    """脱敏无法归类的文献库错误；不记录也不返回原始凭据。"""
    from app.ui.errors import mask_sensitive_text

    safe = mask_sensitive_text(str(value or ""))
    safe = _BEARER_SECRET_PATTERN.sub("Bearer ****MASKED", safe)
    safe = _NAMED_SECRET_PATTERN.sub(r"\1\2****MASKED", safe)
    safe = _QUERY_SECRET_PATTERN.sub(r"\1****MASKED", safe)
    return safe.strip()


def _collect_library_error_values(target: list[Any], value: Any) -> None:
    """从 API/LibraryManager 的多种错误结构中提取待展示值。"""
    if value is None or value == "":
        return
    if isinstance(value, (list, tuple, set)):
        for item in value:
            _collect_library_error_values(target, item)
        return
    if isinstance(value, dict):
        for key in ("error", "message", "reason", "detail"):
            if value.get(key):
                _collect_library_error_values(target, value[key])
                return
        target.append("文献索引失败：服务返回了无法识别的错误格式。")
        return
    target.append(value)


def format_library_errors(payload: Any) -> list[str]:
    """
    将文献索引错误转换为可行动且不泄密的中文提示。

    ``EmbeddingError`` 的稳定错误码及旧版 SDK 异常文本都会被识别；原始
    网络响应、URL、Header 和 Key 不会进入面向用户的提示。
    """
    from app.clients.embedding_client import (
        classify_embedding_error_text,
        embedding_error_guidance,
    )

    result = _as_dict(payload)
    raw_messages: list[Any] = []
    for field in ("errors", "rejected"):
        _collect_library_error_values(raw_messages, result.get(field))
    if not raw_messages:
        _collect_library_error_values(raw_messages, result.get("message"))

    user_messages: list[str] = []
    for raw_value in raw_messages:
        code = classify_embedding_error_text(str(raw_value or ""))
        message = (
            embedding_error_guidance(code)
            if code is not None
            else _safe_library_error_text(raw_value)
        )
        if message and message not in user_messages:
            user_messages.append(message)
    return user_messages or [
        "文献索引失败，原文件未丢失。请稍后重试；若持续失败，请运行 "
        "`py -3 scripts/smoke_bailian.py --embedding`。"
    ]


def _first_int(*values: Any) -> int | None:
    """返回第一个可转换为非负整数的值。"""
    for value in values:
        if value is None or isinstance(value, bool):
            continue
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            continue
        if parsed >= 0:
            return parsed
    return None


def _new_library_manager():
    """
    延迟创建本地文献库服务。

    新实现的规范类名为 ``LibraryManager``；为兼容开发中命名，也接受
    ``LibraryService``。故意不回退到手工落盘 + IndexingService，避免绕过配额、
    删除和题源隔离策略。
    """
    try:
        from app.rag import library_manager as manager_module
    except ImportError as exc:
        raise RuntimeError("本地文献库服务尚未安装（缺少 app.rag.library_manager）。") from exc
    manager_cls = getattr(manager_module, "LibraryManager", None) or getattr(
        manager_module, "LibraryService", None
    )
    if manager_cls is None:
        raise RuntimeError("本地文献库服务缺少 LibraryManager/LibraryService。")
    return manager_cls()


def _call_library_method(manager: Any, names: tuple[str, ...], *args: Any) -> Any:
    """以规范方法名为主，兼容开发中的少量别名。"""
    for name in names:
        method = getattr(manager, name, None)
        if callable(method):
            return method(*args)
        if method is not None and not args:
            return method
    raise RuntimeError(f"本地文献库服务缺少方法：{' / '.join(names)}")


def _normalize_library_status(payload: Any) -> dict:
    """
    将 HTTP/LibraryManager 的状态统一为前端稳定结构。

    核心实现可返回 ``usage/quota/documents``，也兼容早期的顶层字段命名。
    """
    raw = _as_dict(payload)
    documents_raw = raw.get("documents") or raw.get("files") or []
    documents: list[dict] = []
    for value in documents_raw if isinstance(documents_raw, list) else []:
        item = _as_dict(value)
        document_id = item.get("document_id") or item.get("id") or item.get("doc_id")
        documents.append(
            {
                **item,
                "document_id": str(document_id or ""),
                "name": str(item.get("name") or item.get("filename") or item.get("source_name") or "未命名文献"),
                "size_bytes": _first_int(item.get("size_bytes"), item.get("bytes"), item.get("file_size")) or 0,
                "chunk_count": _first_int(item.get("chunk_count"), item.get("chunks")) or 0,
                "created_at": item.get("created_at") or item.get("uploaded_at") or "",
            }
        )

    usage_raw = _as_dict(raw.get("usage"))
    quota_raw = _as_dict(raw.get("quota") or raw.get("limits"))
    used_documents = _first_int(
        usage_raw.get("document_count"), usage_raw.get("file_count"), usage_raw.get("documents"),
        raw.get("document_count"), len(documents)
    )
    used_bytes = _first_int(
        usage_raw.get("total_bytes"), usage_raw.get("used_bytes"), raw.get("total_bytes"), raw.get("used_bytes")
    )
    max_documents = _first_int(
        quota_raw.get("max_documents"), quota_raw.get("max_files"), raw.get("max_documents"), raw.get("max_files")
    )
    max_raw_bytes = _first_int(quota_raw.get("max_raw_bytes"), raw.get("max_raw_bytes"))
    max_index_bytes = _first_int(quota_raw.get("max_index_bytes"), raw.get("max_index_bytes"))
    max_total_bytes = _first_int(
        quota_raw.get("max_total_bytes"), quota_raw.get("total_bytes"), raw.get("max_total_bytes")
    )
    if max_total_bytes is None and max_raw_bytes is not None and max_index_bytes is not None:
        max_total_bytes = max_raw_bytes + max_index_bytes
    max_files_per_upload = _first_int(
        quota_raw.get("max_files_per_upload"), quota_raw.get("max_batch_files"), raw.get("max_files_per_upload")
    )
    max_batch_bytes = _first_int(
        quota_raw.get("max_batch_bytes"), quota_raw.get("max_upload_bytes"), raw.get("max_batch_bytes")
    )
    max_file_bytes = _first_int(quota_raw.get("max_file_bytes"), raw.get("max_file_bytes"))
    policy = _as_dict(raw.get("policy"))

    return {
        **raw,
        "status": str(raw.get("status") or "ok"),
        "documents": documents,
        "usage": {
            **usage_raw,
            "document_count": used_documents or 0,
            "total_bytes": used_bytes or 0,
        },
        "quota": {
            **quota_raw,
            "max_documents": max_documents,
            "max_total_bytes": max_total_bytes,
            "max_raw_bytes": max_raw_bytes,
            "max_index_bytes": max_index_bytes,
            "max_files_per_upload": max_files_per_upload,
            "max_batch_bytes": max_batch_bytes,
            "max_file_bytes": max_file_bytes,
        },
        "policy": {
            **policy,
            "question_source_excluded": bool(
                policy.get("question_source_excluded", raw.get("question_source_excluded", False))
            ),
        },
    }


def get_library_status() -> dict:
    """读取本地文献库配额与文档清单（HTTP 优先，进程内回退）。"""
    try:
        response = requests.get(
            f"{api_base()}/library/status", timeout=_short_timeout_seconds()
        )
        if response.status_code == 200:
            return _normalize_library_status(response.json())
    except (requests.RequestException, ValueError):
        pass

    if _api_only():
        return _normalize_library_status(
            {
                "status": "unavailable",
                "message": "sage125-api 暂不可用。",
                "documents": [],
                "usage": {"document_count": 0, "total_bytes": 0},
                "quota": {},
            }
        )

    try:
        manager = _new_library_manager()
        payload = _call_library_method(manager, ("get_status", "status", "library_status"))
        return _normalize_library_status(payload)
    except Exception as exc:  # noqa: BLE001 - 前端须降级为可读状态
        return _normalize_library_status(
            {
                "status": "unavailable",
                "message": str(exc),
                "documents": [],
                "usage": {"document_count": 0, "total_bytes": 0},
                "quota": {},
            }
        )


def validate_upload_batch(files: list[tuple[str, bytes]], library_status: Optional[dict] = None) -> dict:
    """
    在网络请求/落盘之前检查文件数、总字节、单文件与文献库剩余配额。
    """
    status = _normalize_library_status(library_status or {})
    usage = status.get("usage") or {}
    quota = status.get("quota") or {}
    file_count = len(files)
    total_bytes = sum(len(content) for _name, content in files)
    max_files_value = _first_int(quota.get("max_files_per_upload"))
    max_batch_value = _first_int(quota.get("max_batch_bytes"))
    max_file_value = _first_int(quota.get("max_file_bytes"))
    max_files = _DEFAULT_UPLOAD_MAX_FILES if max_files_value is None else max_files_value
    max_batch_bytes = (_DEFAULT_UPLOAD_TOTAL_MB * 1024 * 1024) if max_batch_value is None else max_batch_value
    max_file_bytes = (_DEFAULT_UPLOAD_MAX_MB * 1024 * 1024) if max_file_value is None else max_file_value
    max_documents = _first_int(quota.get("max_documents"))
    max_total_bytes = _first_int(quota.get("max_raw_bytes"), quota.get("max_total_bytes"))
    used_documents = _first_int(usage.get("document_count")) or 0
    used_bytes = _first_int(usage.get("raw_bytes"), usage.get("total_bytes")) or 0

    validation_errors: list[str] = []
    if file_count == 0:
        validation_errors.append("请先选择文件。")
    if file_count > max_files:
        validation_errors.append(f"单次最多上传 {max_files} 个文件，当前为 {file_count} 个。")
    if total_bytes > max_batch_bytes:
        validation_errors.append(f"本批文件总计 {total_bytes} 字节，超过单次上限 {max_batch_bytes} 字节。")
    if max_documents is not None and used_documents + file_count > max_documents:
        validation_errors.append(f"文献数配额不足：已用 {used_documents}/{max_documents}，本次尝试添加 {file_count} 个。")
    if max_total_bytes is not None and used_bytes + total_bytes > max_total_bytes:
        validation_errors.append(f"存储配额不足：已用 {used_bytes}/{max_total_bytes} 字节。")

    for name, content in files:
        safe_name = Path(name).name
        if Path(safe_name).suffix.lower() not in _SUPPORTED_LIBRARY_EXTENSIONS:
            validation_errors.append(f"{safe_name}: 不支持的文件类型。")
        if len(content) > max_file_bytes:
            validation_errors.append(f"{safe_name}: 文件大小 {len(content)} 字节，超过单文件上限 {max_file_bytes} 字节。")

    return {
        "ok": not validation_errors,
        "errors": validation_errors,
        "file_count": file_count,
        "total_bytes": total_bytes,
        "limits": {
            "max_files": max_files,
            "max_batch_bytes": max_batch_bytes,
            "max_file_bytes": max_file_bytes,
        },
    }


def ingest_files(files: list[tuple[str, bytes]]) -> dict:
    """
    上传文件并加入 RAG 索引（HTTP 优先，回退进程内索引）。

    参数：
        files: (filename, content_bytes) 列表。

    返回：
        ingest 结果字典。
    """
    # UI 外调用也必须经过批次与配额预检，避免绕过组件层。
    precheck = validate_upload_batch(files, get_library_status())
    if not precheck["ok"]:
        return {
            "status": "failed",
            "error_type": "upload_precheck_failed",
            "message": "上传前检查未通过。",
            "errors": precheck["errors"],
            "files": [],
            "chunks_added": 0,
        }

    # 直接提交，不再用短时 GET /health 作为上传门禁。Render Free API 可能正在
    # 冷启动，而 POST 本身有足够的连接/处理等待时间。非幂等上传不自动重试，
    # 避免服务端已完成但响应丢失时重复入库。
    remote_failure: dict | None = None
    try:
        multipart = [("files", (name, content)) for name, content in files]
        r = requests.post(
            f"{api_base()}/ingest",
            files=multipart,
            timeout=(_short_timeout_seconds(), _ingest_timeout_seconds()),
        )
        if r.status_code == 200:
            return r.json()
        try:
            body = r.json()
        except ValueError:
            body = {"message": r.text or f"HTTP {r.status_code}"}
        return {
            **body,
            "status": "failed",
            "error_type": body.get("error_type", "http_error"),
            "files": body.get("files", []),
            "chunks_added": body.get("chunks_added", 0),
        }
    except requests.Timeout:
        remote_failure = {
            "status": "failed",
            "files": [],
            "chunks_added": 0,
            "error_type": "ingest_result_unconfirmed",
            "message": (
                "API 唤醒或索引处理超时，本次上传结果尚未确认。"
                "请先刷新文献清单；确认未入库后再重试。"
            ),
        }
    except requests.RequestException:
        remote_failure = {
            "status": "failed",
            "files": [],
            "chunks_added": 0,
            "error_type": "api_unavailable",
            "message": "sage125-api 正在唤醒或暂不可达，本次上传未写入。请稍后重试。",
        }

    if _api_only():
        return remote_failure or {
            "status": "failed",
            "files": [],
            "chunks_added": 0,
            "error_type": "api_unavailable",
            "message": "sage125-api 正在唤醒或暂不可达，本次上传未写入。请稍后重试。",
        }

    # 回退：与 HTTP /ingest 使用同一 LibraryManager，不允许绕过治理层。
    try:
        manager = _new_library_manager()
        result = _as_dict(
            _call_library_method(manager, ("ingest_files", "add_files", "upload_files"), files)
        )
        if "files" in result:
            indexed_files = result.get("files") or []
        elif "files_indexed" in result:
            indexed_files = result.get("files_indexed") or []
        else:
            indexed_files = [Path(name).name for name, _ in files]
        return {
            **result,
            "status": result.get("status", "ok"),
            "files": indexed_files,
            "chunks_added": result.get("chunks_added", result.get("chunks", 0)),
            "errors": result.get("errors", []),
        }
    except Exception as exc:
        return {
            "status": "failed",
            "files": [],
            "chunks_added": 0,
            "error_type": "library_unavailable",
            "message": f"本地文献库写入失败：{exc}",
            "errors": [str(exc)],
        }


def delete_library_document(document_id: str) -> dict:
    """显式删除文献及其索引数据（HTTP 优先，进程内回退）。"""
    document_id = str(document_id or "").strip()
    if not document_id:
        return {"status": "failed", "message": "缺少 document_id。", "error_type": "invalid_document_id"}

    try:
        response = requests.delete(
            f"{api_base()}/library/documents/{quote(document_id, safe='')}",
            timeout=_short_timeout_seconds(),
        )
        if response.status_code in (200, 202, 204):
            if response.status_code == 204 or not response.content:
                return {"status": "ok", "document_id": document_id}
            return _as_dict(response.json())
        # API 存在时尊重其明确拒绝，避免在另一进程重复删除。
        if response.status_code != 404:
            try:
                body = _as_dict(response.json())
            except ValueError:
                body = {"message": response.text or f"HTTP {response.status_code}"}
            return {**body, "status": "failed", "error_type": body.get("error_type", "http_error")}
    except requests.RequestException:
        pass

    if _api_only():
        return {
            "status": "failed",
            "document_id": document_id,
            "error_type": "api_unavailable",
            "message": "sage125-api 暂不可用，未在 UI 服务内删除数据。",
        }

    try:
        manager = _new_library_manager()
        result = _as_dict(
            _call_library_method(manager, ("delete_document", "remove_document"), document_id)
        )
        return {**result, "status": result.get("status", "ok"), "document_id": document_id}
    except Exception as exc:
        return {
            "status": "failed",
            "document_id": document_id,
            "error_type": "library_unavailable",
            "message": f"删除失败：{exc}",
        }


def recover_run_after_timeout(question_id: str, min_mtime: float | None = None) -> dict | None:
    """
    HTTP 超时后尝试从 exports 恢复已完成的运行（后端可能仍在跑并已成功落盘）。

    参数：
        question_id: 期望的问题 ID。
        min_mtime:   仅考虑此 Unix 时间之后写入的 run 目录。

    返回：
        与 start_run 相同结构的 dict；未找到则 None。
    """
    from app.ui.run_browser import list_runs

    for item in list_runs(limit=30):
        rid = item.get("run_id", "")
        if item.get("question_id") != question_id:
            continue
        run_dir = _exports_dir() / rid
        report = run_dir / "report.json"
        if not report.exists():
            continue
        if min_mtime is not None and report.stat().st_mtime < min_mtime:
            continue
        loaded = get_run(rid)
        if loaded.get("plan"):
            summary = loaded.get("llm_call_summary") or {}
            return {
                "run_id": rid,
                "question_id": question_id,
                "mode": item.get("mode", "real"),
                "status": "completed",
                "plan": loaded["plan"],
                "plan_question_id": loaded["plan"].get("question_id", ""),
                "evidence_cards": loaded.get("evidence_cards") or [],
                "agent_trace": loaded.get("agent_trace") or [],
                "quality_gates": loaded.get("quality_gates") or [],
                "llm_call_summary": summary,
                "warnings": ["recovered_after_http_timeout"],
                "errors": [],
                "mock": loaded.get("mock"),
                "recovered_from_timeout": True,
            }
    return None


def run_preflight(
    use_local_rag: bool = True,
    use_deep_research: bool = True,
    *,
    check_connectivity: bool = False,
    progress_callback: Callable[[dict], None] | None = None,
) -> dict:
    """运行真实模式 preflight；API-only UI 不得加载后端配置或模型客户端。"""
    if _api_only():
        try:
            response = requests.get(
                f"{api_base()}/preflight",
                params={
                    "use_local_rag": use_local_rag,
                    "use_deep_research": use_deep_research,
                },
                timeout=_short_timeout_seconds(),
            )
            if response.status_code == 200:
                return response.json()
        except (requests.RequestException, ValueError):
            pass
        return {
            "ok": False,
            "errors": ["sage125-api 暂不可用。"],
            "warnings": [],
        }
    from app.workflow.preflight import run_real_preflight
    from app.core.run_progress import progress_reporting

    with progress_reporting(progress_callback):
        return run_real_preflight(
            use_local_rag=use_local_rag,
            use_deep_research=use_deep_research,
            check_connectivity=check_connectivity,
        )


def _start_run_inprocess(
    payload: dict,
    mode: str,
    progress_callback: Callable[[dict], None] | None = None,
) -> dict:
    """在 Streamlit 进程内直接运行 pipeline（无 HTTP 超时限制）。"""
    from app.core.logging import mask_text
    from app.core.run_response import build_run_response_from_state, failed_run_response

    question_id = payload["question_id"]
    if mode == "real":
        pf = run_preflight(
            payload["use_local_rag"],
            payload["use_deep_research"],
            check_connectivity=True,
            progress_callback=progress_callback,
        )
        if not pf.get("ok"):
            resp = failed_run_response(
                question_id, mode, pf.get("errors", []), message="preflight 未通过"
            )
            d = resp.to_api_dict()
            d["preflight"] = pf
            d["error_type"] = "preflight_failed"
            return d

    try:
        from app.workflow.pipeline import run_pipeline_with_state

        plan, state = run_pipeline_with_state(
            question_id=question_id,
            user_feedback=payload.get("user_feedback") or None,
            use_local_rag=payload["use_local_rag"],
            use_deep_research=payload["use_deep_research"],
            use_open_literature=payload["use_open_literature"],
            reviewer_auto_revision=payload["reviewer_auto_revision"],
            mock_mode=(mode == "mock"),
            progress_callback=progress_callback,
        )
        status = "completed"
        if state.errors:
            status = "failed"
        elif state.warnings and any("deep_research_failed" in w for w in state.warnings):
            status = "partial_failed"
        resp = build_run_response_from_state(
            question_id=question_id, mode=mode, state=state, plan=plan, status=status, message=status
        )
        return resp.to_api_dict()
    except Exception as exc:
        err = mask_text(str(exc))
        resp = failed_run_response(
            question_id,
            mode,
            [err],
            message="pipeline 异常",
            run_id=getattr(exc, "run_id", None),
        )
        d = resp.to_api_dict()
        d["error_type"] = type(exc).__name__
        return d


def start_run(
    question_id: str,
    feedback: str,
    switches: dict,
    mode: str = "mock",
    progress_callback: Callable[[dict], None] | None = None,
) -> dict:
    """
    启动一次 pipeline 运行（HTTP 优先，回退进程内）。

    参数：
        question_id: 问题 ID。
        feedback:    可选用户反馈。
        switches:    能力开关字典。
        mode:        "mock" | "real"。

    返回：
        运行结果字典（含 question_id / plan.question_id / llm_call_summary）。
    """
    payload = {
        "question_id": question_id,
        "mode": mode,
        "user_feedback": feedback or "",
        "use_deep_research": switches.get("use_deep_research", True),
        "use_open_literature": switches.get("use_open_literature", True),
        "use_local_rag": switches.get("use_local_rag", True),
        "reviewer_auto_revision": switches.get("reviewer_auto_revision", True),
    }
    # 默认进程内运行（真实模式常需 15–25 分钟，HTTP 易触发读超时）。
    if _prefer_inprocess_run():
        return _start_run_inprocess(payload, mode, progress_callback=progress_callback)

    if not api_available():
        return {
            "status": "failed",
            "errors": ["sage125-api 暂不可用，未在 UI 服务内执行模型调用。"],
            "mock": mode == "mock",
            "error_type": "api_unavailable",
        }

    # 显式 FRONTEND_RUN_VIA_API=1 时走 HTTP；超时后尝试从 exports 恢复。
    import time

    started_at = time.time()
    timeout_s = _run_timeout_seconds(mode, payload.get("use_deep_research", False))
    if progress_callback:
        progress_callback({
            "stage": "preflight", "status": "waiting", "percent": 4,
            "message": "已交给本地 API，正在等待真实运行进度",
        })
    try:
        r = requests.post(f"{api_base()}/runs", json=payload, timeout=timeout_s)
        if r.status_code == 200:
            if progress_callback:
                progress_callback({"stage": "completed", "status": "completed", "percent": 100,
                                   "message": "AI Scientist 运行完成"})
            return {**r.json(), "mock": mode == "mock"}
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {"errors": [r.text]}
        return {**body, "status": body.get("status", "failed"), "mock": mode == "mock", "error_type": "http_error"}
    except requests.exceptions.ReadTimeout:
        recovered = recover_run_after_timeout(question_id, min_mtime=started_at - 5)
        if recovered:
            return recovered
        return {
            "status": "failed",
            "errors": [
                f"真实模式运行超时（{timeout_s}s）。可先关闭 DeepResearch 或运行 smoke_bailian 检查百炼链路。"
            ],
            "mock": mode == "mock",
            "error_type": "read_timeout",
        }
    except requests.RequestException as exc:
        err = str(exc)
        if "Read timed out" in err or "read timeout" in err.lower():
            recovered = recover_run_after_timeout(question_id, min_mtime=started_at - 5)
            if recovered:
                return recovered
            return {
                "status": "failed",
                "errors": [err],
                "mock": mode == "mock",
                "error_type": "read_timeout",
            }
        return {"status": "failed", "errors": [err], "mock": mode == "mock", "error_type": "connection_error"}


def run_experiment(question_id: str) -> dict:
    """
    触发一次真实实验执行（HTTP 优先，回退进程内）。

    目前仅 Q028 有可执行的科学入口；其它题目服务端会诚实返回
    ``available=False``，前端不编造结果。
    """
    qid = str(question_id or "").strip()
    try:
        r = requests.post(
            f"{api_base()}/experiments/{quote(qid, safe='')}/run",
            timeout=max(_short_timeout_seconds(), 60),
        )
        if r.status_code == 200:
            return r.json()
    except requests.RequestException:
        pass
    if _api_only():
        return {
            "question_id": qid,
            "available": False,
            "status": "not_available",
            "reason": "sage125-api 暂不可用，无法运行真实实验。",
        }
    from app.api.routes import run_experiment as _run_experiment

    return _run_experiment(qid)


def get_experiment_canonical_status(question_id: str) -> dict:
    """
    只读地获取旗舰案例 canonical package / 原子发布状态（HTTP 优先，回退进程内）。

    绝不在此调用中触发实验执行或发布动作；仅读取现有磁盘证据与已发布的
    canonical pointer（如有）。
    """
    qid = str(question_id or "").strip()
    try:
        r = requests.get(
            f"{api_base()}/experiments/{quote(qid, safe='')}/canonical-status",
            timeout=_short_timeout_seconds(),
        )
        if r.status_code == 200:
            return r.json()
    except requests.RequestException:
        pass
    if _api_only():
        return {
            "question_id": qid,
            "available": False,
            "status": "not_available",
            "reason": "sage125-api 暂不可用，无法读取 canonical 状态。",
        }
    from app.api.routes import get_experiment_canonical_status as _get_status

    return _get_status(qid)


def get_experiment_actual_ablation_01(question_id: str) -> dict:
    """只读获取 Q028 ACTUAL-ABLATION-01 状态（HTTP 优先，回退进程内）。"""
    qid = str(question_id or "").strip()
    try:
        r = requests.get(
            f"{api_base()}/experiments/{quote(qid, safe='')}/ablations/actual-ablation-01",
            timeout=_short_timeout_seconds(),
        )
        if r.status_code == 200:
            return r.json()
    except requests.RequestException:
        pass
    if _api_only():
        return {
            "question_id": qid,
            "available": False,
            "status": "not_available",
            "reason": "sage125-api 暂不可用，无法读取消融状态。",
        }
    from app.api.routes import get_experiment_actual_ablation_01 as _get_status

    return _get_status(qid)


def get_llm_calls(run_id: str) -> dict:
    """获取某次运行的脱敏 LLM 调用审计（HTTP 优先，回退读取本地文件）。"""
    if api_available():
        try:
            r = requests.get(
                f"{api_base()}/runs/{run_id}/llm-calls",
                timeout=_short_timeout_seconds(),
            )
            if r.status_code == 200:
                return r.json()
        except requests.RequestException:
            pass
    if _api_only():
        return {"exists": False, "status": "unavailable", "records": [], "summary": {}}
    from app.ui.run_browser import get_llm_call_audit

    return get_llm_call_audit(run_id)


def get_run(run_id: str) -> dict:
    """读取某次运行产物（HTTP 优先，回退读取 exports）。"""
    if api_available():
        try:
            r = requests.get(
                f"{api_base()}/runs/{run_id}", timeout=_short_timeout_seconds()
            )
            if r.status_code == 200:
                return r.json()
        except requests.RequestException:
            pass
    if _api_only():
        return {"status": "unavailable", "message": "sage125-api 暂不可用。"}
    run_dir = _exports_dir() / run_id
    if not run_dir.exists():
        return {"status": "missing", "message": f"运行不存在：{run_id}"}

    def _rj(p: Path):
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    plan = _rj(run_dir / "report.json")
    audit = _rj(run_dir / "llm_call_audit.json") or {}
    return {
        "run_id": run_id, "plan": plan,
        "question_id": (plan or {}).get("question_id", ""),
        "evidence_cards": _rj(run_dir / "evidence_cards.json"),
        "agent_trace": _rj(run_dir / "agent_trace.json"),
        "quality_gates": _rj(run_dir / "quality_gates.json"),
        "llm_call_summary": audit.get("summary", {}),
        "mock": audit.get("run_mode") == "mock" if audit else None,
    }


def revise_run(run_id: str, feedback: str) -> dict:
    """触发反馈修订（HTTP 优先，回退进程内）。"""
    if api_available():
        try:
            r = requests.post(f"{api_base()}/runs/{run_id}/feedback", json={"feedback": feedback}, timeout=_run_timeout_seconds("real"))
            if r.status_code == 200:
                return r.json()
            return {"status": "failed", "message": r.text}
        except requests.RequestException as exc:
            return {"status": "failed", "message": str(exc)}
    if _api_only():
        return {
            "status": "failed",
            "error_type": "api_unavailable",
            "message": "sage125-api 暂不可用。",
        }
    from app.workflow.pipeline import revise_with_feedback

    try:
        plan = revise_with_feedback(run_id, feedback)
        return {"run_id": run_id, "status": "revised", "plan": plan.model_dump(),
                "revision_history": plan.revision_history}
    except ValueError as exc:
        # 非法反馈被拒绝。
        return {"status": "rejected", "message": str(exc)}
    except FileNotFoundError as exc:
        return {"status": "failed", "message": str(exc)}


def local_file_path(run_id: str, file_name: str) -> Optional[Path]:
    """返回某运行产物文件的本地路径（存在则返回，否则 None）。"""
    p = _exports_dir() / run_id / file_name
    return p if p.exists() else None


def read_local_file(run_id: str, file_name: str) -> Optional[bytes]:
    """读取某运行产物文件内容字节（不存在返回 None）。"""
    p = local_file_path(run_id, file_name)
    return p.read_bytes() if p else None
