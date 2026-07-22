"""
app.rag.indexing_service —— 文件索引服务。

统一封装“加载 -> 切分 -> 嵌入 -> 写入向量库”的索引流程，供脚本与后续
FastAPI /ingest 端点复用。支持基于 hash 的重复跳过与用户上传标记。

安全：
    - 用户上传资料 metadata.is_user_upload=True，绝不发送到公开文献 API；
    - 对前端只返回文件名，不暴露完整绝对路径。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from app.clients.embedding_client import EmbeddingClient
from app.core.logging import get_logger
from app.rag.chunker import chunk_documents
from app.rag.document_loader import Document, UnsupportedFileTypeError, load_any
from app.rag.zvec_store import get_vector_store

# 模块级日志器。
logger = get_logger("rag.indexing_service")


def _mock_embedding_enabled() -> bool:
    """
    判断是否启用确定性 mock 嵌入（环境变量 MOCK_EMBEDDING=true）。

    返回：
        True 表示使用 deterministic hash 向量（仅测试用）。
    """
    return os.getenv("MOCK_EMBEDDING", "").strip().lower() in ("1", "true", "yes")


def mock_embed(texts: list[str], dim: int = 64) -> list[list[float]]:
    """
    确定性 mock 嵌入：由文本 hash 生成稳定向量（仅测试用，不可用于正式评审）。

    参数：
        texts: 文本列表。
        dim:   向量维度。

    返回：
        与输入等长的确定性向量列表。
    """
    import hashlib

    vectors: list[list[float]] = []
    for text in texts:
        # 用文本 sha256 派生确定性伪随机向量。
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        # 循环取字节生成 dim 维，归一到 [-1,1]。
        vec = [((digest[i % len(digest)] / 255.0) * 2 - 1) for i in range(dim)]
        vectors.append(vec)
    return vectors


class IndexingService:
    """文件索引服务：将若干文件索引到向量库。"""

    def __init__(
        self,
        embedding_client: Optional[EmbeddingClient] = None,
        index_dir: str = "data/index/zvec",
    ) -> None:
        """
        初始化索引服务。

        参数：
            embedding_client: 嵌入客户端；缺省新建（真实模式使用百炼）。
            index_dir:        zvec 索引目录。
        """
        # 允许注入嵌入客户端以便测试。
        self.embedding_client = embedding_client
        self.index_dir = index_dir
        # 已索引 hash 集合（基于 chunks.jsonl 恢复，用于重复跳过）。
        self._indexed_hashes: set[str] = self._load_indexed_hashes()

    def _load_indexed_hashes(self) -> set[str]:
        """从与当前向量库配套的 chunks.jsonl 恢复跨重启去重集合。"""
        hashes: set[str] = set()
        chunks_path = Path(self.index_dir).parent / "chunks.jsonl"
        if not chunks_path.exists():
            return hashes
        try:
            for line in chunks_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                source_hash = (record.get("metadata") or {}).get("source_hash")
                if source_hash:
                    hashes.add(str(source_hash))
        except OSError as exc:
            logger.warning("读取既有 chunks.jsonl 失败，将继续但不做跨重启去重：%s", exc)
        return hashes

    def _embed(self, texts: list[str]) -> list[list[float]]:
        """
        对文本执行嵌入（尊重 MOCK_EMBEDDING）。

        参数：
            texts: 文本列表。

        返回：
            向量列表。
        """
        # mock 模式使用确定性向量。
        if _mock_embedding_enabled():
            return mock_embed(texts)
        # 真实模式使用百炼嵌入客户端。
        client = self.embedding_client or EmbeddingClient()
        return client.embed_texts(texts)

    def index_files(
        self,
        paths: list[str],
        is_user_upload: bool = False,
        force_rebuild: bool = False,
        metadata_overrides: Optional[dict] = None,
        max_chunks: Optional[int] = None,
    ) -> dict:
        """
        索引一批文件。

        参数：
            paths:          文件路径列表。
            is_user_upload: 是否为用户上传（影响 metadata 与检索范围）。
            force_rebuild:  是否强制重建（忽略 hash 去重）。
            metadata_overrides: 写入每个 Document 的安全、稳定来源元数据。
            max_chunks:     本次最多允许写入的 chunk 数；超限时不做嵌入或写库。

        返回：
            结果字典：
                {"status","files_indexed","documents","chunks","index_dir","errors"}
            其中 files_indexed 仅含文件名（不暴露绝对路径）。
        """
        files_indexed: list[str] = []
        errors: list[str] = []
        all_documents: list[Document] = []

        # 逐个加载文件，单个失败不影响整体。
        for path in paths:
            try:
                docs = load_any(path, is_user_upload=is_user_upload)
                if metadata_overrides:
                    for doc in docs:
                        doc.metadata.update(metadata_overrides)
                all_documents.extend(docs)
                # 仅记录文件名，保护隐私。
                files_indexed.append(Path(path).name)
            except (FileNotFoundError, UnsupportedFileTypeError, RuntimeError) as exc:
                errors.append(f"{Path(path).name}: {exc}")

        # 无可索引文档时提前返回。
        if not all_documents:
            return {
                "status": "failed" if errors else "ok",
                "files_indexed": files_indexed,
                "documents": 0,
                "chunks": 0,
                "chunk_ids": [],
                "index_dir": self.index_dir,
                "errors": errors,
            }

        # 切分为 chunk。
        chunks = chunk_documents(all_documents)
        # hash 去重（除非强制重建）。
        if not force_rebuild:
            chunks = [c for c in chunks if c.metadata.get("source_hash") not in self._indexed_hashes]
        if max_chunks is not None and len(chunks) > max_chunks:
            errors.append(f"chunk_limit_exceeded: {len(chunks)} > {max_chunks}")
            return {
                "status": "failed",
                "files_indexed": files_indexed,
                "documents": len(all_documents),
                "chunks": 0,
                "chunk_ids": [],
                "candidate_chunks": len(chunks),
                "index_dir": self.index_dir,
                "errors": errors,
            }
        # 无新增 chunk。
        if not chunks:
            return {
                "status": "ok",
                "files_indexed": files_indexed,
                "documents": len(all_documents),
                "chunks": 0,
                "chunk_ids": [],
                "index_dir": self.index_dir,
                "errors": errors,
            }

        # 嵌入 + 写入向量库。
        try:
            embeddings = self._embed([c.text for c in chunks])
            store = get_vector_store(dimension=len(embeddings[0]) if embeddings else None, index_dir=self.index_dir)
            store.add_documents(chunks, embeddings)
            store.persist()
            # 记录已索引 hash。
            for c in chunks:
                h = c.metadata.get("source_hash")
                if h:
                    self._indexed_hashes.add(h)
        except Exception as exc:
            errors.append(f"index_write_failed: {exc}")
            return {
                "status": "failed",
                "files_indexed": files_indexed,
                "documents": len(all_documents),
                "chunks": 0,
                "chunk_ids": [],
                "index_dir": self.index_dir,
                "errors": errors,
            }

        logger.info(
            "index_files 完成：files=%d，documents=%d，chunks=%d",
            len(files_indexed),
            len(all_documents),
            len(chunks),
        )
        return {
            "status": "ok",
            "files_indexed": files_indexed,
            "documents": len(all_documents),
            "chunks": len(chunks),
            "chunk_ids": [c.chunk_id for c in chunks],
            "index_dir": self.index_dir,
            "errors": errors,
        }
