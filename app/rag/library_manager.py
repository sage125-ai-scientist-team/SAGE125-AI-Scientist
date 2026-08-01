"""持久化用户文献库：上传、去重、配额、索引状态与显式删除。

`sjtu-booklet.pdf` 是 125 个问题的题源，不属于用户文献。真实研究流水线只打开
本模块管理的独立索引，因此题源不会混入 Evidence Wall 或 References。
"""

from __future__ import annotations

import hashlib
import csv
import io
import json
import os
import re
import shutil
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from app.contracts.rag import (
    IndexConfig,
    SourcePolicy,
    SourceRecord,
    SourceRole,
    SourceType,
)
from app.core.config import PROJECT_ROOT, Settings, get_settings
from app.core.logging import get_logger
from app.rag.indexing_service import IndexingService
from app.rag.source_policy import RegistrySourcePolicy
from app.rag.zvec_store import get_vector_store

logger = get_logger("rag.library_manager")

USER_LIBRARY_UPLOADS_DIR = PROJECT_ROOT / "data" / "raw" / "uploads"
USER_LIBRARY_INDEX_ROOT = PROJECT_ROOT / "data" / "index" / "user_library"
USER_LIBRARY_ZVEC_DIR = USER_LIBRARY_INDEX_ROOT / "zvec"
USER_LIBRARY_CHUNKS_PATH = USER_LIBRARY_INDEX_ROOT / "chunks.jsonl"
USER_LIBRARY_MANIFEST_PATH = USER_LIBRARY_UPLOADS_DIR / ".library_manifest.json"

_SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".csv"}
_RESERVED_SOURCE_NAME = "sjtu-booklet.pdf"
_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
_LIBRARY_LOCK = threading.RLock()


class LibraryValidationError(ValueError):
    """上传内容、文件名或容量不符合文献库规则。"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_filename(raw_name: str) -> str:
    """生成仅用于展示/存储的安全文件名，并阻止题源混入文献库。"""
    # Path 在 Windows 上不会把反斜杠视为 POSIX 分隔符，先统一分隔符。
    name = (raw_name or "").replace("\\", "/").split("/")[-1].strip()
    name = re.sub(r"[\x00-\x1f<>:\"/\\|?*]", "_", name).strip(" .")
    if not name:
        raise LibraryValidationError("文件名为空或不合法。")
    ext = Path(name).suffix.lower()
    if ext not in _SUPPORTED_EXTENSIONS:
        raise LibraryValidationError("仅支持 PDF、TXT、MD、CSV。")
    if Path(name).stem.upper() in _WINDOWS_RESERVED:
        raise LibraryValidationError("文件名是 Windows 保留名称。")
    if len(name) > 180:
        stem_limit = max(1, 180 - len(ext))
        name = f"{Path(name).stem[:stem_limit]}{ext}"
    return name


def _validate_content(name: str, content: bytes) -> None:
    """做低成本类型嗅探，避免把明显错误或二进制内容送入解析器。"""
    if not content:
        raise LibraryValidationError("文件为空。")
    ext = Path(name).suffix.lower()
    if ext == ".pdf" and not content.lstrip().startswith(b"%PDF-"):
        raise LibraryValidationError("文件扩展名为 PDF，但内容不是有效 PDF。")
    if ext in {".txt", ".md", ".csv"} and b"\x00" in content[:8192]:
        raise LibraryValidationError("文本文件包含二进制 NUL 字节。")


def _decode_text(content: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gbk"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise LibraryValidationError("文本编码无法识别（支持 UTF-8/UTF-8-SIG/GBK）。")


def _dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for item in path.rglob("*"):
        try:
            if item.is_file() and not item.name.endswith(".tmp"):
                total += item.stat().st_size
        except OSError:
            continue
    return total


def _disk_free_bytes(disk_usage: Any) -> int:
    """兼容 shutil namedtuple 与测试桩对象，读取可用磁盘字节数。"""
    if hasattr(disk_usage, "free"):
        return int(disk_usage.free)
    return int(disk_usage[2])


def _disk_total_bytes(disk_usage: Any) -> int:
    if hasattr(disk_usage, "total"):
        return int(disk_usage.total)
    return int(disk_usage[0])


class LibraryManager:
    """管理永久保留、跨问题复用的本地用户文献库。"""

    def __init__(
        self,
        settings: Settings | None = None,
        uploads_dir: str | Path | None = None,
        index_dir: str | Path | None = None,
        manifest_path: str | Path | None = None,
        indexing_service_factory: Callable[..., Any] | None = None,
        disk_usage_fn: Callable[[str | os.PathLike[str]], Any] | None = None,
        vector_store_factory: Callable[..., Any] | None = None,
        index_config: IndexConfig | None = None,
        source_registry: Mapping[str, SourceRecord] | None = None,
        source_policy: SourcePolicy | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        configured_data_root = Path(getattr(self.settings, "data_dir", "data"))
        if not configured_data_root.is_absolute():
            configured_data_root = PROJECT_ROOT / configured_data_root
        self.index_config = index_config or IndexConfig.resolve(
            {"data_root": configured_data_root}
        )
        default_uploads_dir = self.index_config.data_root / "raw" / "uploads"
        self.uploads_dir = Path(uploads_dir or default_uploads_dir)
        self.index_dir = Path(index_dir or self.index_config.vector_index_dir)
        self.index_root = self.index_dir.parent
        self.chunks_manifest_path = (
            self.index_root / "chunks.jsonl"
            if index_dir is not None
            else self.index_config.chunks_manifest_path
        )
        self.manifest_path = Path(manifest_path or (self.uploads_dir / ".library_manifest.json"))
        self.indexing_service_factory = indexing_service_factory or IndexingService
        self.disk_usage_fn = disk_usage_fn or shutil.disk_usage
        self.vector_store_factory = vector_store_factory or get_vector_store
        self.source_registry = {
            str(content_hash).strip().lower(): SourceRecord.model_validate(record)
            for content_hash, record in (source_registry or {}).items()
        }
        self.source_policy = source_policy or RegistrySourcePolicy()
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self._cleanup_stale_parts()

    def _setting(self, name: str, default: int) -> int:
        return int(getattr(self.settings, name, default))

    def _float_setting(self, name: str, default: float) -> float:
        return float(getattr(self.settings, name, default))

    def _stored_files(self) -> list[Path]:
        """列出真实原文文件；排除清单与临时文件。"""
        if not self.uploads_dir.exists():
            return []
        return [
            path
            for path in self.uploads_dir.iterdir()
            if path.is_file()
            and path != self.manifest_path
            and not path.name.endswith((".tmp", ".part"))
        ]

    def _raw_disk_bytes(self) -> int:
        total = 0
        for path in self._stored_files():
            try:
                total += path.stat().st_size
            except OSError:
                continue
        return total

    def _indexed_chunk_ids(self) -> set[str]:
        ids: set[str] = set()
        chunks_path = self.chunks_manifest_path
        if not chunks_path.exists():
            return ids
        try:
            for line in chunks_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    chunk_id = json.loads(line).get("chunk_id")
                except json.JSONDecodeError:
                    continue
                if chunk_id:
                    ids.add(str(chunk_id))
        except OSError:
            return ids
        return ids

    def _empty_manifest(self) -> dict[str, Any]:
        return {"version": 1, "updated_at": _utc_now(), "documents": []}

    def _load_manifest(self) -> dict[str, Any]:
        if not self.manifest_path.exists():
            return self._empty_manifest()
        try:
            data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            if not isinstance(data.get("documents"), list):
                raise ValueError("documents 必须是列表")
            return data
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise RuntimeError(f"本地文献库清单损坏：{exc}") from exc

    def _save_manifest(self, manifest: dict[str, Any]) -> None:
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest["updated_at"] = _utc_now()
        tmp = self.manifest_path.with_name(f"{self.manifest_path.name}.{uuid.uuid4().hex}.tmp")
        tmp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.manifest_path)

    def _cleanup_stale_parts(self) -> None:
        """只清理 24 小时前的临时文件；正式文献永不自动删除。"""
        cutoff = datetime.now(timezone.utc).timestamp() - 86400
        for path in self.uploads_dir.glob("*.part"):
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink()
            except OSError:
                continue

    def _public_document(self, record: dict[str, Any]) -> dict[str, Any]:
        # 不返回 stored_name、绝对路径或完整 SHA-256。
        return {
            "document_id": record.get("document_id", ""),
            "name": record.get("original_name", ""),
            "size_bytes": int(record.get("size_bytes", 0)),
            "uploaded_at": record.get("uploaded_at", ""),
            "status": record.get("status", "unknown"),
            "chunk_count": int(record.get("chunk_count", 0)),
            "error": record.get("error", ""),
        }

    def get_status(self) -> dict[str, Any]:
        """返回可安全展示的容量、索引和文档清单。"""
        with _LIBRARY_LOCK:
            manifest = self._load_manifest()
            docs = manifest["documents"]
            raw_bytes = max(
                sum(int(d.get("size_bytes", 0)) for d in docs),
                self._raw_disk_bytes(),
            )
            index_bytes = _dir_size(self.index_root)
            manifest_chunk_count = sum(int(d.get("chunk_count", 0)) for d in docs)
            actual_chunk_count = len(self._indexed_chunk_ids())
            chunk_count = max(manifest_chunk_count, actual_chunk_count)
            indexed = sum(1 for d in docs if d.get("status") == "indexed")
            failed = sum(1 for d in docs if d.get("status") == "index_failed")
            try:
                disk = self.disk_usage_fn(str(self.uploads_dir))
                free_bytes = _disk_free_bytes(disk)
                total_disk_bytes = _disk_total_bytes(disk)
            except (OSError, TypeError, IndexError):
                free_bytes = -1
                total_disk_bytes = -1
            configured_reserve = self._setting("library_min_free_mb", 5120) * 1024 * 1024
            percent_reserve = (
                int(total_disk_bytes * self._float_setting("library_min_free_percent", 5.0) / 100.0)
                if total_disk_bytes >= 0
                else 0
            )
            effective_reserve = max(configured_reserve, percent_reserve)
            status = "empty" if not docs else ("degraded" if failed else "ready")
            return {
                "status": status,
                "index_status": "ready" if indexed else "empty",
                "persistent": True,
                "retention": "until_explicit_delete",
                "cross_question_reuse": True,
                "question_source_excluded": _RESERVED_SOURCE_NAME,
                "documents": [self._public_document(d) for d in docs],
                "usage": {
                    "file_count": len(docs),
                    "indexed_file_count": indexed,
                    "failed_file_count": failed,
                    "raw_bytes": raw_bytes,
                    "index_bytes": index_bytes,
                    "total_bytes": raw_bytes + index_bytes,
                    "chunk_count": chunk_count,
                    "orphan_chunk_count": max(0, actual_chunk_count - manifest_chunk_count),
                    "disk_free_bytes": free_bytes,
                    "orphan_file_count": max(0, len(self._stored_files()) - len(docs)),
                },
                "limits": {
                    "max_file_bytes": self._setting("max_upload_mb", 25) * 1024 * 1024,
                    "max_batch_files": self._setting("library_max_batch_files", 10),
                    "max_batch_bytes": self._setting("library_max_batch_mb", 100) * 1024 * 1024,
                    "max_files": self._setting("library_max_files", 500),
                    "max_raw_bytes": self._setting("library_max_raw_mb", 2048) * 1024 * 1024,
                    "max_index_bytes": self._setting("library_max_index_mb", 4096) * 1024 * 1024,
                    "max_chunks": self._setting("library_max_chunks", 100000),
                    "max_chunks_per_file": self._setting("library_max_chunks_per_file", 5000),
                    "min_free_bytes": effective_reserve,
                    "min_free_percent": self._float_setting("library_min_free_percent", 5.0),
                },
                "privacy_notice": (
                    "原文件和向量保存在本项目；不会发送给 arXiv/OpenAlex/Crossref。"
                    "真实索引会把切分后的文本发送给百炼 text-embedding 模型生成向量。"
                ),
            }

    # 兼容调用方常见命名。
    status = get_status

    def _check_batch_limits(self, files: list[tuple[str, bytes]]) -> None:
        max_files = self._setting("library_max_batch_files", 10)
        if not files:
            raise LibraryValidationError("没有收到文件。")
        if len(files) > max_files:
            raise LibraryValidationError(f"单批最多上传 {max_files} 个文件。")
        batch_bytes = sum(len(content) for _, content in files)
        max_batch = self._setting("library_max_batch_mb", 100) * 1024 * 1024
        if batch_bytes > max_batch:
            raise LibraryValidationError(
                f"单批总大小超过 {self._setting('library_max_batch_mb', 100)} MB。"
            )

    def _check_structure_limits(self, name: str, content: bytes) -> None:
        """在落盘/嵌入前限制 PDF 页数、文本字符和 CSV 规模。"""
        ext = Path(name).suffix.lower()
        if ext == ".pdf":
            try:
                import fitz

                doc = fitz.open(stream=content, filetype="pdf")
                pages = int(doc.page_count)
                doc.close()
            except ImportError:
                # 缺依赖会在索引阶段给出明确错误，不把文献原文丢掉。
                return
            except Exception as exc:
                raise LibraryValidationError(f"PDF 无法解析：{exc}") from exc
            limit = self._setting("library_max_pdf_pages", 2000)
            if pages > limit:
                raise LibraryValidationError(f"PDF 共 {pages} 页，超过 {limit} 页上限。")
            return

        text = _decode_text(content)
        char_limit = self._setting("library_max_text_chars", 10000000)
        if len(text) > char_limit:
            raise LibraryValidationError(f"文本字符数超过 {char_limit} 上限。")
        if ext != ".csv":
            return
        row_limit = self._setting("library_max_csv_rows", 250000)
        column_limit = self._setting("library_max_csv_columns", 200)
        try:
            reader = csv.reader(io.StringIO(text))
            for row_index, row in enumerate(reader, start=1):
                if row_index > row_limit + 1:  # 含一行表头
                    raise LibraryValidationError(f"CSV 数据行超过 {row_limit} 上限。")
                if len(row) > column_limit:
                    raise LibraryValidationError(
                        f"CSV 第 {row_index} 行有 {len(row)} 列，超过 {column_limit} 列上限。"
                    )
        except csv.Error as exc:
            raise LibraryValidationError(f"CSV 格式无法解析：{exc}") from exc

    def _store_file(self, stored_name: str, content: bytes) -> Path:
        dest = self.uploads_dir / stored_name
        if dest.exists():
            return dest
        tmp = self.uploads_dir / f"{stored_name}.{uuid.uuid4().hex}.part"
        tmp.write_bytes(content)
        tmp.replace(dest)
        return dest

    def _effective_disk_reserve(self, total_disk_bytes: int) -> int:
        """Return the configured absolute/percentage reserve, whichever is larger."""
        reserve = self._setting("library_min_free_mb", 5120) * 1024 * 1024
        if total_disk_bytes >= 0:
            reserve = max(
                reserve,
                int(
                    total_disk_bytes
                    * self._float_setting("library_min_free_percent", 5.0)
                    / 100.0
                ),
            )
        return reserve

    def _index_capacity_error(self) -> str:
        """Check limits that apply before both a new index and an index retry."""
        max_index = self._setting("library_max_index_mb", 4096) * 1024 * 1024
        if _dir_size(self.index_root) >= max_index:
            return "向量索引容量已达到上限。"
        try:
            disk = self.disk_usage_fn(str(self.uploads_dir))
            free_bytes = _disk_free_bytes(disk)
            total_disk_bytes = _disk_total_bytes(disk)
        except (OSError, TypeError, IndexError):
            return ""
        if free_bytes <= self._effective_disk_reserve(total_disk_bytes):
            return "磁盘剩余空间低于安全保留线，暂不重试索引。"
        return ""

    def _retry_source_path(self, record: dict[str, Any]) -> Path:
        """Revalidate a retained original before using it for an index retry.

        The manifest is persistent state and can be edited outside the process, so
        a retry must not trust its path, size, name, or digest blindly.
        """
        stored_name = str(record.get("stored_name", ""))
        if not stored_name or Path(stored_name).name != stored_name:
            raise LibraryValidationError("文献清单中的存储文件名不安全。")

        path = self.uploads_dir / stored_name
        if path.is_symlink():
            raise LibraryValidationError("文献原文件不能是符号链接。")
        try:
            resolved = path.resolve(strict=True)
            uploads_root = self.uploads_dir.resolve(strict=True)
        except OSError as exc:
            raise LibraryValidationError("已保存的文献原文件不存在。") from exc
        if resolved.parent != uploads_root or not resolved.is_file():
            raise LibraryValidationError("文献原文件不在受管文献库目录中。")

        original_name = str(record.get("original_name", ""))
        if _safe_filename(original_name) != original_name:
            raise LibraryValidationError("文献清单中的原文件名不安全。")
        content = resolved.read_bytes()
        max_file_bytes = self._setting("max_upload_mb", 25) * 1024 * 1024
        if len(content) > max_file_bytes:
            raise LibraryValidationError(
                f"原文件超过单文件 {self._setting('max_upload_mb', 25)} MB 上限。"
            )
        if len(content) != int(record.get("size_bytes", -1)):
            raise LibraryValidationError("已保存的原文件大小与文献清单不一致。")
        if hashlib.sha256(content).hexdigest() != str(record.get("sha256", "")):
            raise LibraryValidationError("已保存的原文件内容校验失败。")
        _validate_content(original_name, content)
        self._check_structure_limits(original_name, content)
        return resolved

    def _index_record(self, record: dict[str, Any], path: Path, manifest: dict[str, Any]) -> int:
        capacity_error = self._index_capacity_error()
        if capacity_error:
            record.update(status="index_failed", error=capacity_error, chunk_count=0, chunk_ids=[])
            return 0

        current_chunks = max(
            sum(int(d.get("chunk_count", 0)) for d in manifest["documents"]),
            len(self._indexed_chunk_ids()),
        )
        remaining = self._setting("library_max_chunks", 100000) - current_chunks
        max_for_file = min(self._setting("library_max_chunks_per_file", 5000), remaining)
        if max_for_file <= 0:
            record.update(status="index_failed", error="本地文献库 chunk 总量已达上限。")
            return 0

        logical_source = f"library://{record['document_id']}/{record['original_name']}"
        overrides = {
            "source_path": logical_source,
            "source_name": record["original_name"],
            "doc_id": record["document_id"],
            "library_document_id": record["document_id"],
            "source_id": record["source_id"],
            "content_sha256": record["content_hash"],
            "source_type": record["source_type"],
            "source_role": record["source_role"],
            "is_user_upload": True,
        }
        try:
            service = self.indexing_service_factory(index_dir=str(self.index_dir))
            result = service.index_files(
                [str(path)],
                is_user_upload=True,
                metadata_overrides=overrides,
                max_chunks=max_for_file,
            )
        except Exception as exc:
            result = {"status": "failed", "chunks": 0, "chunk_ids": [], "errors": [str(exc)]}

        if result.get("status") != "ok":
            errors = [str(x) for x in result.get("errors", [])]
            record.update(
                status="index_failed",
                error="；".join(errors)[:500] or "索引失败。",
                chunk_count=0,
                chunk_ids=[],
            )
            return 0

        chunk_ids = [str(x) for x in result.get("chunk_ids", [])]
        record.update(
            status="indexed",
            indexed_at=_utc_now(),
            error="",
            chunk_count=int(result.get("chunks", len(chunk_ids))),
            chunk_ids=chunk_ids,
        )

        # 单文件写入后再检查真实索引体积；超限则立即撤销新向量，原文件仍永久保留。
        max_index = self._setting("library_max_index_mb", 4096) * 1024 * 1024
        if _dir_size(self.index_root) > max_index:
            try:
                store = self.vector_store_factory(index_dir=str(self.index_dir))
                store.delete_documents(chunk_ids)
                store.persist()
            except Exception as exc:
                logger.error("索引超限回滚失败：%s", exc)
            record.update(
                status="index_failed",
                error="索引容量超过上限；已停止加入新文献。",
                chunk_count=0,
                chunk_ids=[],
            )
            return 0

        # Embeddings and vector writes also consume disk.  Roll back the new
        # chunks if this operation crossed the reserve line.
        try:
            disk = self.disk_usage_fn(str(self.uploads_dir))
            free_bytes = _disk_free_bytes(disk)
            total_disk_bytes = _disk_total_bytes(disk)
        except (OSError, TypeError, IndexError):
            free_bytes = -1
            total_disk_bytes = -1
        if free_bytes >= 0 and free_bytes < self._effective_disk_reserve(total_disk_bytes):
            try:
                store = self.vector_store_factory(index_dir=str(self.index_dir))
                store.delete_documents(chunk_ids)
                store.persist()
            except Exception as exc:
                logger.error("索引越过磁盘保留线后的回滚失败：%s", exc)
            record.update(
                status="index_failed",
                error="索引写入后磁盘空间低于安全保留线；新增向量已回滚。",
                chunk_count=0,
                chunk_ids=[],
            )
            return 0
        return int(record["chunk_count"])

    def ingest_files(self, files: list[tuple[str, bytes]]) -> dict[str, Any]:
        """永久保存并索引一批文件；按内容 SHA-256 跨重启去重。"""
        with _LIBRARY_LOCK:
            try:
                self._check_batch_limits(files)
            except LibraryValidationError as exc:
                return {
                    "status": "failed", "files": [], "documents": [], "chunks_added": 0,
                    "duplicates": [], "rejected": [str(exc)], "errors": [str(exc)],
                    "index_status": self.get_status()["index_status"],
                }

            manifest = self._load_manifest()
            existing_by_sha = {str(d.get("sha256")): d for d in manifest["documents"]}
            accepted: list[str] = []
            duplicate_names: list[str] = []
            rejected: list[str] = []
            index_errors: list[str] = []
            public_docs: list[dict[str, Any]] = []
            chunks_added = 0

            max_file_bytes = self._setting("max_upload_mb", 25) * 1024 * 1024
            for raw_name, raw_content in files:
                content = bytes(raw_content)
                try:
                    name = _safe_filename(raw_name)
                    _validate_content(name, content)
                    self._check_structure_limits(name, content)
                    if len(content) > max_file_bytes:
                        raise LibraryValidationError(
                            f"{name}: 超过单文件 {self._setting('max_upload_mb', 25)} MB 上限。"
                        )
                except (LibraryValidationError, TypeError, ValueError) as exc:
                    rejected.append(f"{raw_name or '未命名文件'}: {exc}")
                    continue

                digest = hashlib.sha256(content).hexdigest()
                try:
                    source = self.source_policy.classify_source(
                        filename=name,
                        content_hash=digest,
                        registry=self.source_registry,
                    )
                except (TypeError, ValueError) as exc:
                    rejected.append(f"{name}: 来源分类失败：{exc}")
                    continue
                if (
                    source.source_type is SourceType.BOOKLET
                    or source.source_role is SourceRole.QUESTION_SOURCE
                ):
                    rejected.append(f"{name}: 问题来源不能加入本地文献库。")
                    continue
                existing = existing_by_sha.get(digest)
                if existing is not None:
                    existing.update(
                        source_id=source.source_id,
                        content_hash=source.content_hash,
                        source_type=source.source_type.value,
                        source_role=source.source_role.value,
                    )
                    self._save_manifest(manifest)
                    duplicate_names.append(name)
                    stored_path = self.uploads_dir / str(existing.get("stored_name", ""))
                    if not stored_path.exists():
                        stored_path = self._store_file(str(existing["stored_name"]), content)
                    # 先前因网络/配置失败的文献，重复上传时自动重试索引。
                    if existing.get("status") != "indexed":
                        chunks_added += self._index_record(existing, stored_path, manifest)
                        self._save_manifest(manifest)
                        if existing.get("status") != "indexed":
                            index_errors.append(
                                f"{name}: 原文件已保留，但索引失败：{existing.get('error') or '未知原因'}"
                            )
                    public_docs.append(self._public_document(existing))
                    continue

                current_raw = max(
                    sum(int(d.get("size_bytes", 0)) for d in manifest["documents"]),
                    self._raw_disk_bytes(),
                )
                actual_file_count = max(len(manifest["documents"]), len(self._stored_files()))
                if actual_file_count >= self._setting("library_max_files", 500):
                    rejected.append(f"{name}: 文献数量已达上限。")
                    continue
                if current_raw + len(content) > self._setting("library_max_raw_mb", 2048) * 1024 * 1024:
                    rejected.append(f"{name}: 原文件库容量将超过上限。")
                    continue
                if _dir_size(self.index_root) >= self._setting("library_max_index_mb", 4096) * 1024 * 1024:
                    rejected.append(f"{name}: 向量索引容量已达上限。")
                    continue
                try:
                    disk = self.disk_usage_fn(str(self.uploads_dir))
                    free_bytes = _disk_free_bytes(disk)
                    total_disk_bytes = _disk_total_bytes(disk)
                except (OSError, TypeError, IndexError):
                    free_bytes = -1
                    total_disk_bytes = -1
                min_free = self._setting("library_min_free_mb", 5120) * 1024 * 1024
                if total_disk_bytes >= 0:
                    min_free = max(
                        min_free,
                        int(
                            total_disk_bytes
                            * self._float_setting("library_min_free_percent", 5.0)
                            / 100.0
                        ),
                    )
                if free_bytes >= 0 and free_bytes - len(content) < min_free:
                    rejected.append(f"{name}: 磁盘剩余空间低于安全保留线。")
                    continue

                document_id = f"DOC-{digest[:16]}"
                stored_name = f"{digest[:16]}-{name}"
                path = self._store_file(stored_name, content)
                record = {
                    "document_id": document_id,
                    "sha256": digest,
                    "source_id": source.source_id,
                    "content_hash": source.content_hash,
                    "source_type": source.source_type.value,
                    "source_role": source.source_role.value,
                    "original_name": name,
                    "stored_name": stored_name,
                    "size_bytes": len(content),
                    "uploaded_at": _utc_now(),
                    "status": "stored",
                    "chunk_count": 0,
                    "chunk_ids": [],
                    "error": "",
                }
                manifest["documents"].append(record)
                existing_by_sha[digest] = record
                self._save_manifest(manifest)
                chunks_added += self._index_record(record, path, manifest)
                self._save_manifest(manifest)
                accepted.append(name)
                public_docs.append(self._public_document(record))
                if record.get("status") != "indexed":
                    index_errors.append(
                        f"{name}: 原文件已保留，但索引失败：{record.get('error') or '未知原因'}"
                    )

            if index_errors:
                status = "partial"
            else:
                status = "ok" if not rejected else ("partial" if accepted or duplicate_names else "failed")
            library_status = self.get_status()
            return {
                "status": status,
                "files": accepted,
                "documents": public_docs,
                "chunks_added": chunks_added,
                "duplicates": duplicate_names,
                "rejected": rejected,
                "errors": rejected + index_errors,
                "index_status": library_status["index_status"],
                "library": library_status,
            }

    def retry_document(self, document_id: str) -> dict[str, Any]:
        """Retry indexing from the permanently retained original file.

        No upload bytes or caller-provided path are accepted here.  Before the
        embedding call, the managed file is revalidated against the manifest and
        all current chunk/index/disk quotas are applied again.
        """
        with _LIBRARY_LOCK:
            manifest = self._load_manifest()
            record = next(
                (d for d in manifest["documents"] if d.get("document_id") == document_id),
                None,
            )
            if record is None:
                return {
                    "status": "not_found",
                    "document_id": document_id,
                    "retried": False,
                    "chunks_added": 0,
                }
            if record.get("status") == "indexed":
                return {
                    "status": "ok",
                    "document_id": document_id,
                    "retried": False,
                    "chunks_added": 0,
                    "message": "文献已经完成索引，无需重试。",
                    "document": self._public_document(record),
                    "library": self.get_status(),
                }

            record["retry_count"] = int(record.get("retry_count", 0)) + 1
            record["last_retry_at"] = _utc_now()
            try:
                path = self._retry_source_path(record)
            except (LibraryValidationError, OSError, ValueError) as exc:
                record.update(
                    status="index_failed",
                    error=f"重试前原文件校验失败：{str(exc)[:400]}",
                    chunk_count=0,
                    chunk_ids=[],
                )
                self._save_manifest(manifest)
                return {
                    "status": "failed",
                    "document_id": document_id,
                    "retried": False,
                    "chunks_added": 0,
                    "message": record["error"],
                    "document": self._public_document(record),
                    "library": self.get_status(),
                }

            # Persist the transient state so a process interruption is visible
            # and can itself be retried safely on the next request.
            record.update(status="indexing", error="")
            self._save_manifest(manifest)
            chunks_added = self._index_record(record, path, manifest)
            self._save_manifest(manifest)
            succeeded = record.get("status") == "indexed"
            return {
                "status": "ok" if succeeded else "failed",
                "document_id": document_id,
                "retried": True,
                "chunks_added": chunks_added,
                "message": "索引重试成功。" if succeeded else str(record.get("error") or "索引重试失败。"),
                "document": self._public_document(record),
                "library": self.get_status(),
            }

    def retry_failed_documents(self) -> dict[str, Any]:
        """Retry every ``index_failed`` document, one at a time, from local originals."""
        with _LIBRARY_LOCK:
            manifest = self._load_manifest()
            document_ids = [
                str(record.get("document_id", ""))
                for record in manifest["documents"]
                if record.get("status") == "index_failed" and record.get("document_id")
            ]
            results: list[dict[str, Any]] = []
            chunks_added = 0
            for document_id in document_ids:
                result = dict(self.retry_document(document_id))
                result.pop("library", None)
                chunks_added += int(result.get("chunks_added", 0))
                results.append(result)

            succeeded = sum(1 for result in results if result.get("status") == "ok")
            failed = len(results) - succeeded
            status = "ok" if failed == 0 else ("partial" if succeeded else "failed")
            return {
                "status": status,
                "attempted_count": len(document_ids),
                "retried_count": sum(1 for result in results if result.get("retried")),
                "succeeded_count": succeeded,
                "failed_count": failed,
                "chunks_added": chunks_added,
                "results": results,
                "library": self.get_status(),
            }

    def delete_document(self, document_id: str) -> dict[str, Any]:
        """仅在用户显式请求时删除原文件、向量、元数据与清单记录。"""
        with _LIBRARY_LOCK:
            manifest = self._load_manifest()
            record = next(
                (d for d in manifest["documents"] if d.get("document_id") == document_id), None
            )
            if record is None:
                return {"status": "not_found", "document_id": document_id, "deleted": False}

            chunk_ids = [str(x) for x in record.get("chunk_ids", [])]
            if chunk_ids:
                try:
                    store = self.vector_store_factory(index_dir=str(self.index_dir))
                    store.delete_documents(chunk_ids)
                    store.persist()
                except Exception as exc:
                    logger.warning("删除文献向量失败，保留原文件与清单以便重试：%s", exc)
                    return {
                        "status": "failed", "document_id": document_id, "deleted": False,
                        "message": f"向量删除失败：{str(exc)[:300]}",
                    }

            path = self.uploads_dir / str(record.get("stored_name", ""))
            try:
                if path.exists():
                    path.unlink()
            except OSError as exc:
                return {
                    "status": "failed", "document_id": document_id, "deleted": False,
                    "message": f"原文件删除失败：{str(exc)[:300]}",
                }
            manifest["documents"] = [
                d for d in manifest["documents"] if d.get("document_id") != document_id
            ]
            self._save_manifest(manifest)
            return {
                "status": "ok",
                "document_id": document_id,
                "name": record.get("original_name", ""),
                "deleted": True,
                "library": self.get_status(),
            }


# 旧/第三方调用者可使用更通用的名称。
LibraryService = LibraryManager
