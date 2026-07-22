"""
app.rag.zvec_store —— 向量存储封装（生产用 zvec，测试用 MemoryVectorStore）。

设计原则：
    - 不臆测 zvec API：提供 inspect_zvec_capabilities() 做能力探测并落盘；
    - 生产默认使用 ZvecVectorStore（本地 in-process，无需 API Key / Docker / 独立服务）；
    - 仅当 MOCK_VECTOR_STORE=true 时才允许使用 MemoryVectorStore（测试专用）；
    - zvec 导入失败或 API 不兼容时抛出清晰异常，绝不静默降级。

元数据安全：
    向量库内的标量 metadata 可能受实现限制，故额外将全部 chunk metadata
    另存为 data/index/chunks.jsonl，避免向量库 metadata 丢失。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Protocol, runtime_checkable

from app.core.logging import get_logger
from app.rag.chunker import Chunk

# 模块级日志器。
logger = get_logger("rag.zvec_store")

# 默认能力探测输出路径。
_CAPABILITIES_PATH = Path("data/index/zvec_capabilities.json")


class ZvecCompatibilityError(Exception):
    """当本地 zvec 版本的 API 与本封装不兼容时抛出。"""


@dataclass
class SearchResult:
    """向量检索的单条结果。"""

    # 命中片段 ID。
    chunk_id: str
    # 相关性分数（归一化到 0-1，越大越相关）。
    score: float
    # 命中片段文本。
    text: str
    # 命中片段元数据。
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class VectorStoreProtocol(Protocol):
    """向量存储协议：定义统一的增/查/持久化接口。"""

    def add_documents(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        """添加片段及其向量。"""
        ...

    def search(
        self, query_embedding: list[float], top_k: int, filters: dict | None = None
    ) -> list[SearchResult]:
        """按向量相似度检索。"""
        ...

    def persist(self) -> None:
        """持久化索引与元数据。"""
        ...

    def load(self) -> None:
        """加载已有索引与元数据。"""
        ...

    def delete_documents(self, chunk_ids: list[str]) -> int:
        """按 chunk ID 删除向量与配套元数据，返回实际删除的元数据条数。"""
        ...


def inspect_zvec_capabilities() -> dict:
    """
    探测本地 zvec 的可用性与关键 API，并将结果写入 data/index/zvec_capabilities.json。

    返回：
        探测结果字典（installed / version / 关键符号存在性）。
    """
    caps: dict[str, Any] = {
        "installed": False,
        "version": None,
        "symbols": {},
    }
    try:
        import zvec

        caps["installed"] = True
        caps["version"] = getattr(zvec, "__version__", None)
        # 检查本封装依赖的关键符号是否存在。
        for name in [
            "create_and_open",
            "open",
            "Collection",
            "CollectionSchema",
            "FieldSchema",
            "VectorSchema",
            "Doc",
            "Query",
            "DataType",
            "MetricType",
            "FlatIndexParam",
        ]:
            caps["symbols"][name] = hasattr(zvec, name)
    except ImportError as exc:
        # 未安装：记录原因，不抛异常（探测本身应可运行）。
        caps["error"] = f"import_failed: {exc}"

    # 落盘探测结果，便于按本地版本适配。
    try:
        _CAPABILITIES_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CAPABILITIES_PATH.write_text(
            json.dumps(caps, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError:
        logger.warning("无法写入 zvec_capabilities.json（忽略）。")
    return caps


def _relevance_from_score(score: float) -> float:
    """
    将 zvec 的 COSINE 距离分数转换为 0-1 相关性（越大越相关）。

    参数：
        score: zvec 返回的分数（COSINE 距离，0 表示完全相同）。

    返回：
        归一化相关性，范围 [0,1]。
    """
    # COSINE 距离 -> 相关性；夹取到 [0,1]。
    return max(0.0, min(1.0, 1.0 - float(score)))


class ZvecVectorStore:
    """
    基于 zvec 的生产向量存储。

    首次 add_documents 时按向量维度创建集合（FLAT + COSINE）；
    metadata 另存 chunks.jsonl 以防向量库 metadata 丢失。
    """

    def __init__(
        self,
        index_dir: str = "data/index/zvec",
        collection_name: str = "sage125",
        dimension: Optional[int] = None,
    ) -> None:
        """
        初始化 zvec 向量存储（此时不建立连接，惰性创建/打开集合）。

        参数：
            index_dir:       集合持久化目录。
            collection_name: 集合名。
            dimension:       向量维度；None 表示首次插入时自动记录。

        异常：
            ZvecCompatibilityError: 当 zvec 未安装或关键 API 缺失时抛出。
        """
        # 校验 zvec 可用性与关键符号。
        caps = inspect_zvec_capabilities()
        if not caps["installed"]:
            raise ZvecCompatibilityError(
                "zvec 初始化失败，请确认 pip install zvec。"
                "测试可设置 MOCK_VECTOR_STORE=true 使用 MemoryVectorStore。"
            )
        missing = [k for k, v in caps["symbols"].items() if not v]
        if missing:
            raise ZvecCompatibilityError(
                f"zvec API 不兼容，缺少符号：{missing}。请根据本地 zvec 版本适配 zvec_store.py。"
            )
        # 保存配置。
        self.index_dir = Path(index_dir)
        self.collection_name = collection_name
        self.dimension = dimension
        # 集合对象惰性获取。
        self._collection = None
        # chunks.jsonl 与向量库同目录的上一级（data/index/chunks.jsonl）。
        self._chunks_jsonl = self.index_dir.parent / "chunks.jsonl"
        # 内存中的 chunk_id -> metadata 映射（load 后填充，用于结果补全）。
        self._meta_map: dict[str, dict] = {}

    def _ensure_collection(self, create_if_missing: bool):
        """
        惰性获取 zvec 集合（打开或创建）。

        参数：
            create_if_missing: 集合不存在时是否创建（add 时为 True，search 时为 False）。

        返回：
            zvec Collection 对象。

        异常：
            ZvecCompatibilityError: 打开/创建失败或维度未知时抛出。
        """
        # 已获取则复用。
        if self._collection is not None:
            return self._collection
        import shutil

        import zvec

        # 判断集合目录是否已存在有效内容（zvec 集合会在目录内产生文件）。
        exists = self.index_dir.exists() and any(self.index_dir.iterdir())
        try:
            if exists:
                # 打开已有集合。
                self._collection = zvec.open(str(self.index_dir))
            else:
                if not create_if_missing:
                    raise ZvecCompatibilityError("集合不存在且不允许创建（search 前需先构建索引）。")
                if not self.dimension:
                    raise ZvecCompatibilityError("创建集合需要已知向量维度。")
                # create_and_open 会自行创建集合目录；清理可能残留的空目录，仅确保父目录存在。
                if self.index_dir.exists():
                    shutil.rmtree(self.index_dir, ignore_errors=True)
                self.index_dir.parent.mkdir(parents=True, exist_ok=True)
                # 定义 schema：文本 + 元数据 JSON + 向量（FLAT/COSINE）。
                text_field = zvec.FieldSchema("text", zvec.DataType.STRING, nullable=True)
                meta_field = zvec.FieldSchema("meta", zvec.DataType.STRING, nullable=True)
                vec = zvec.VectorSchema(
                    "embedding",
                    zvec.DataType.VECTOR_FP32,
                    dimension=self.dimension,
                    index_param=zvec.FlatIndexParam(metric_type=zvec.MetricType.COSINE),
                )
                schema = zvec.CollectionSchema(
                    name=self.collection_name, fields=[text_field, meta_field], vectors=[vec]
                )
                self._collection = zvec.create_and_open(str(self.index_dir), schema)
        except ZvecCompatibilityError:
            raise
        except Exception as exc:
            # 任何 zvec 层错误统一转为兼容性异常，提示适配。
            raise ZvecCompatibilityError(f"zvec 集合打开/创建失败：{exc}") from exc
        return self._collection

    def add_documents(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        """
        添加片段及其向量到 zvec，并追加写 chunks.jsonl。

        参数：
            chunks:     片段列表。
            embeddings: 与 chunks 等长的向量列表。

        异常：
            ValueError:            数量不一致或维度不一致时抛出。
            ZvecCompatibilityError: zvec 操作失败时抛出。
        """
        # 数量一致性校验。
        if len(chunks) != len(embeddings):
            raise ValueError("chunks 与 embeddings 数量不一致。")
        if not chunks:
            return
        # 首次插入记录维度；后续校验一致。
        dim = len(embeddings[0])
        if self.dimension is None:
            self.dimension = dim
        elif self.dimension != dim:
            raise ValueError(f"向量维度不一致：期望 {self.dimension}，实际 {dim}。")

        import zvec

        collection = self._ensure_collection(create_if_missing=True)
        docs = []
        for chunk, emb in zip(chunks, embeddings):
            # 每个片段的向量维度必须一致。
            if len(emb) != self.dimension:
                raise ValueError(f"片段 {chunk.chunk_id} 向量维度不一致。")
            docs.append(
                zvec.Doc(
                    id=chunk.chunk_id,
                    fields={"text": chunk.text, "meta": json.dumps(chunk.metadata, ensure_ascii=False)},
                    vectors={"embedding": list(emb)},
                )
            )
        try:
            collection.insert(docs)
            collection.flush()
        except Exception as exc:
            raise ZvecCompatibilityError(f"zvec 插入失败：{exc}") from exc

        # 追加写 chunks.jsonl（元数据副本）。
        self._append_chunks_jsonl(chunks)

    def _append_chunks_jsonl(self, chunks: list[Chunk]) -> None:
        """
        将片段元数据追加写入 data/index/chunks.jsonl。

        参数：
            chunks: 片段列表。

        返回：
            None。
        """
        # 确保父目录存在。
        self._chunks_jsonl.parent.mkdir(parents=True, exist_ok=True)
        with self._chunks_jsonl.open("a", encoding="utf-8") as f:
            for chunk in chunks:
                record = {
                    "chunk_id": chunk.chunk_id,
                    "text": chunk.text,
                    "metadata": chunk.metadata,
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                # 同步内存映射。
                self._meta_map[chunk.chunk_id] = chunk.metadata

    def search(
        self, query_embedding: list[float], top_k: int, filters: dict | None = None
    ) -> list[SearchResult]:
        """
        按向量相似度检索；filters 在 Python 层做等值过滤（先取 top_k*5 再截取）。

        参数：
            query_embedding: 查询向量。
            top_k:           返回条数。
            filters:         元数据等值过滤条件（如 {"is_user_upload": True}）。

        返回：
            SearchResult 列表（按相关性降序，长度 <= top_k）；无索引时返回空列表。
        """
        import zvec

        # 无集合可查时返回空（不报错）。
        try:
            collection = self._ensure_collection(create_if_missing=False)
        except ZvecCompatibilityError:
            logger.info("zvec 集合不存在，search 返回空列表。")
            return []

        # 有 filter 时多取候选，便于 Python 层过滤后仍有足够结果。
        fetch_k = top_k * 5 if filters else top_k
        try:
            docs = collection.query(
                queries=zvec.Query(field_name="embedding", vector=list(query_embedding)),
                topk=fetch_k,
                output_fields=["text", "meta"],
            )
        except Exception as exc:
            raise ZvecCompatibilityError(f"zvec 查询失败：{exc}") from exc

        results: list[SearchResult] = []
        for doc in docs:
            # 解析文本与元数据。
            text = doc.field("text") if doc.has_field("text") else ""
            meta_raw = doc.field("meta") if doc.has_field("meta") else "{}"
            try:
                metadata = json.loads(meta_raw) if meta_raw else {}
            except (json.JSONDecodeError, TypeError):
                metadata = {}
            # Python 层过滤。
            if filters and not self._match_filters(metadata, filters):
                continue
            results.append(
                SearchResult(
                    chunk_id=doc.id,
                    score=_relevance_from_score(doc.score if doc.score is not None else 1.0),
                    text=text,
                    metadata=metadata,
                )
            )
        # 截取到 top_k。
        return results[:top_k]

    @staticmethod
    def _match_filters(metadata: dict, filters: dict) -> bool:
        """
        判断元数据是否满足所有等值过滤条件。

        参数：
            metadata: 片段元数据。
            filters:  过滤条件（键值等值）。

        返回：
            True 表示全部条件满足。
        """
        # 支持的过滤键：source_type/file_type/is_user_upload/domain 等，逐一等值比较。
        for key, value in filters.items():
            if metadata.get(key) != value:
                return False
        return True

    def persist(self) -> None:
        """持久化索引（flush 到磁盘）。"""
        # zvec 为文件型存储，flush 即落盘。
        if self._collection is not None:
            try:
                self._collection.flush()
            except Exception as exc:
                raise ZvecCompatibilityError(f"zvec flush 失败：{exc}") from exc

    def load(self) -> None:
        """加载已有索引，并从 chunks.jsonl 恢复元数据映射。"""
        # 打开集合。
        self._ensure_collection(create_if_missing=False)
        # 恢复 chunks.jsonl 元数据映射。
        if self._chunks_jsonl.exists():
            for line in self._chunks_jsonl.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                    self._meta_map[rec["chunk_id"]] = rec["metadata"]
                except (json.JSONDecodeError, KeyError):
                    continue

    def delete_documents(self, chunk_ids: list[str]) -> int:
        """从 zvec 和 chunks.jsonl 同步删除指定片段。"""
        ids = list(dict.fromkeys(str(x) for x in chunk_ids if x))
        if not ids:
            return 0

        # 向量集合不存在时仍清理元数据；这使失败恢复和幂等删除都安全。
        try:
            collection = self._ensure_collection(create_if_missing=False)
            collection.delete(ids)
            collection.flush()
        except ZvecCompatibilityError:
            logger.warning("删除片段时 zvec 集合不存在，仅清理 chunks.jsonl。")
        except Exception as exc:
            raise ZvecCompatibilityError(f"zvec 删除失败：{exc}") from exc

        removed = 0
        id_set = set(ids)
        if self._chunks_jsonl.exists():
            kept: list[str] = []
            for line in self._chunks_jsonl.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    kept.append(line)
                    continue
                if str(rec.get("chunk_id", "")) in id_set:
                    removed += 1
                else:
                    kept.append(json.dumps(rec, ensure_ascii=False))
            tmp = self._chunks_jsonl.with_suffix(".jsonl.tmp")
            tmp.write_text(("\n".join(kept) + "\n") if kept else "", encoding="utf-8")
            tmp.replace(self._chunks_jsonl)
        for chunk_id in ids:
            self._meta_map.pop(chunk_id, None)
        return removed


class MemoryVectorStore:
    """
    内存向量存储（仅用于测试与 MOCK_VECTOR_STORE=true）。

    使用 numpy 余弦相似度，不写生产索引。
    """

    def __init__(self, dimension: Optional[int] = None) -> None:
        """
        初始化内存向量存储。

        参数：
            dimension: 向量维度；None 表示首次插入时记录。
        """
        # 明确日志标记：仅测试用。
        logger.warning("MemoryVectorStore is for testing only（请勿用于生产索引）。")
        self.dimension = dimension
        # 存储 (chunk, embedding) 对。
        self._chunks: list[Chunk] = []
        self._embeddings: list[list[float]] = []

    def add_documents(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        """
        添加片段及向量到内存。

        参数：
            chunks:     片段列表。
            embeddings: 向量列表。

        异常：
            ValueError: 数量或维度不一致时抛出。
        """
        # 数量一致性。
        if len(chunks) != len(embeddings):
            raise ValueError("chunks 与 embeddings 数量不一致。")
        if not chunks:
            return
        # 维度记录与校验。
        dim = len(embeddings[0])
        if self.dimension is None:
            self.dimension = dim
        elif self.dimension != dim:
            raise ValueError(f"向量维度不一致：期望 {self.dimension}，实际 {dim}。")
        for emb in embeddings:
            if len(emb) != self.dimension:
                raise ValueError("存在维度不一致的向量。")
        # 追加存储。
        self._chunks.extend(chunks)
        self._embeddings.extend(embeddings)

    def search(
        self, query_embedding: list[float], top_k: int, filters: dict | None = None
    ) -> list[SearchResult]:
        """
        余弦相似度检索。

        参数：
            query_embedding: 查询向量。
            top_k:           返回条数。
            filters:         元数据等值过滤。

        返回：
            SearchResult 列表（按相似度降序，长度 <= top_k）。

        异常：
            ValueError: 查询向量维度与索引不一致时抛出。
        """
        import numpy as np

        # 无数据返回空。
        if not self._embeddings:
            return []
        # 维度校验。
        if self.dimension and len(query_embedding) != self.dimension:
            raise ValueError(f"查询向量维度不一致：期望 {self.dimension}，实际 {len(query_embedding)}。")

        # 计算余弦相似度。
        mat = np.array(self._embeddings, dtype=float)
        q = np.array(query_embedding, dtype=float)
        # 归一化避免除零。
        mat_norm = np.linalg.norm(mat, axis=1) + 1e-12
        q_norm = np.linalg.norm(q) + 1e-12
        sims = (mat @ q) / (mat_norm * q_norm)

        # 组装并过滤。
        scored: list[SearchResult] = []
        for idx, sim in enumerate(sims):
            chunk = self._chunks[idx]
            if filters and not ZvecVectorStore._match_filters(chunk.metadata, filters):
                continue
            scored.append(
                SearchResult(
                    chunk_id=chunk.chunk_id,
                    score=float(max(0.0, min(1.0, (sim + 1) / 2))),
                    text=chunk.text,
                    metadata=chunk.metadata,
                )
            )
        # 按分数降序，截取 top_k。
        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:top_k]

    def persist(self) -> None:
        """内存存储不持久化（仅测试用）。"""
        # 明确不落盘。
        logger.debug("MemoryVectorStore.persist 为空操作（测试用）。")

    def load(self) -> None:
        """内存存储无持久化可加载（仅测试用）。"""
        # 明确无操作。
        logger.debug("MemoryVectorStore.load 为空操作（测试用）。")

    def delete_documents(self, chunk_ids: list[str]) -> int:
        """删除测试内存库中的指定片段。"""
        id_set = {str(x) for x in chunk_ids if x}
        if not id_set:
            return 0
        kept_chunks: list[Chunk] = []
        kept_embeddings: list[list[float]] = []
        removed = 0
        for chunk, embedding in zip(self._chunks, self._embeddings):
            if chunk.chunk_id in id_set:
                removed += 1
            else:
                kept_chunks.append(chunk)
                kept_embeddings.append(embedding)
        self._chunks = kept_chunks
        self._embeddings = kept_embeddings
        return removed


def get_vector_store(dimension: Optional[int] = None, index_dir: str = "data/index/zvec"):
    """
    工厂：根据 MOCK_VECTOR_STORE 环境变量返回合适的向量存储实现。

    参数：
        dimension: 向量维度（可选）。
        index_dir: zvec 索引目录。

    返回：
        MemoryVectorStore（MOCK_VECTOR_STORE=true）或 ZvecVectorStore（默认）。
    """
    # 仅当显式开启 mock 时使用内存实现，否则使用生产 zvec。
    if os.getenv("MOCK_VECTOR_STORE", "").strip().lower() in ("1", "true", "yes"):
        return MemoryVectorStore(dimension=dimension)
    return ZvecVectorStore(index_dir=index_dir, dimension=dimension)
