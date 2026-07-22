"""
app.rag.chunker —— 文档切分器。

将 Document 切分为带重叠的 Chunk，兼顾中英文长度估计与语义完整：
    段落优先 -> 句子 -> 硬切。每个 Chunk 保留来源与位置元数据，
    并生成稳定 hash（source_hash）用于去重与增量索引。
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger
from app.rag.document_loader import Document

# 模块级日志器。
logger = get_logger("rag.chunker")


@dataclass
class Chunk:
    """可索引的文本片段：文本 + 来源/位置元数据。"""

    # 片段稳定 ID。
    chunk_id: str
    # 片段文本。
    text: str
    # 元数据（含来源、页码、位置、hash 等）。
    metadata: dict[str, Any] = field(default_factory=dict)


def estimate_length(text: str) -> int:
    """
    估算中英文混合文本的“长度”（近似 token 数）。

    规则：
        - 中文（及 CJK）字符每个计 1；
        - 非中文部分按空格分词近似计数。
    无需调用外部 tokenizer。

    参数：
        text: 输入文本。

    返回：
        估算的长度（整数）。
    """
    # 统计 CJK 字符数。
    cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
    # 去除 CJK 后，按空白分词估算英文 token。
    non_cjk = re.sub(r"[\u4e00-\u9fff]", " ", text)
    words = len([w for w in non_cjk.split() if w])
    return cjk + words


def _split_paragraphs(text: str) -> list[str]:
    """
    按空行/换行将文本切为段落。

    参数：
        text: 输入文本。

    返回：
        非空段落列表。
    """
    # 以一个或多个换行分段。
    parts = re.split(r"\n{1,}", text)
    return [p.strip() for p in parts if p.strip()]


def _split_sentences(text: str) -> list[str]:
    """
    按中英文句末标点切分句子。

    参数：
        text: 输入段落文本。

    返回：
        句子列表。
    """
    # 在 . ! ? 。！？ 后切分，保留分隔符。
    parts = re.split(r"(?<=[.!?。！？])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def _hard_split(text: str, max_chars: int) -> list[str]:
    """
    对超长文本按字符硬切。

    参数：
        text:      输入文本。
        max_chars: 单块最大字符数。

    返回：
        硬切后的片段列表。
    """
    # 逐段截取固定长度。
    return [text[i : i + max_chars] for i in range(0, len(text), max_chars)]


def compute_source_hash(text: str, source_path: str, page: Any) -> str:
    """
    基于 chunk 文本 + 来源路径 + 页码生成稳定 hash。

    参数：
        text:        片段文本。
        source_path: 来源文件路径。
        page:        页码（或行范围标识）。

    返回：
        16 位十六进制 hash（截断的 sha256）。
    """
    # 拼接关键字段后计算 sha256，取前 16 位，兼顾稳定与紧凑。
    raw = f"{source_path}|{page}|{text}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def _accumulate_units(units: list[str], chunk_size: int) -> list[str]:
    """
    将文本单元（段/句）贪心累积为不超过 chunk_size 的组合块。

    参数：
        units:      文本单元列表。
        chunk_size: 单块目标长度（近似 token）。

    返回：
        组合后的文本块列表。
    """
    blocks: list[str] = []
    buf = ""
    for unit in units:
        # 单个单元本身超长：先 flush，再按句/硬切拆分。
        if estimate_length(unit) > chunk_size:
            if buf:
                blocks.append(buf)
                buf = ""
            # 段落过长 -> 句子级。
            sentences = _split_sentences(unit)
            if len(sentences) > 1:
                blocks.extend(_accumulate_units(sentences, chunk_size))
            else:
                # 句子仍过长 -> 硬切（按字符近似 chunk_size*2）。
                blocks.extend(_hard_split(unit, chunk_size * 2))
            continue
        # 累加后仍在预算内则合并，否则 flush。
        candidate = (buf + " " + unit).strip() if buf else unit
        if estimate_length(candidate) <= chunk_size:
            buf = candidate
        else:
            if buf:
                blocks.append(buf)
            buf = unit
    if buf:
        blocks.append(buf)
    return blocks


def chunk_documents(
    documents: list[Document],
    chunk_size: int = 1000,
    overlap: int = 180,
    min_chunk_chars: int = 120,
) -> list[Chunk]:
    """
    将 Document 列表切分为可追溯的 Chunk 列表。

    参数：
        documents:       待切分文档。
        chunk_size:      单块目标长度（近似 token/字符），默认 1000。
        overlap:         相邻块重叠长度，默认 180。
        min_chunk_chars: 最小块字符数，过短则尝试合并或跳过。

    返回：
        Chunk 列表（已按 source_hash 去重）。

    异常：
        ValueError: 当 overlap > chunk_size * 0.3 时抛出。
    """
    # 重叠不得过大，否则冗余与成本失控。
    if overlap > chunk_size * 0.3:
        raise ValueError(
            f"overlap({overlap}) 不得超过 chunk_size*0.3({chunk_size * 0.3})。"
        )

    chunks: list[Chunk] = []
    # 已见 hash，用于去重。
    seen_hashes: set[str] = set()

    for doc in documents:
        source_path = doc.metadata.get("source_path", "")
        page = doc.metadata.get("page")
        # 段落优先累积为块。
        paragraphs = _split_paragraphs(doc.text)
        blocks = _accumulate_units(paragraphs, chunk_size)

        # 待合并的过短块缓冲。
        pending_short = ""
        char_cursor = 0
        for block in blocks:
            text = block.strip()
            if not text:
                continue
            # 过短块处理：先尝试与相邻短块合并。
            is_question_title = text.endswith("?") and len(text) < min_chunk_chars
            if len(text) < min_chunk_chars and not is_question_title:
                pending_short = (pending_short + " " + text).strip()
                # 合并后仍不足则继续累积，足够则作为一个块落地。
                if len(pending_short) < min_chunk_chars:
                    continue
                text = pending_short
                pending_short = ""

            # 记录字符区间（近似，用于溯源）。
            char_start = char_cursor
            char_end = char_cursor + len(text)
            char_cursor = char_end - overlap if char_end - overlap > char_start else char_end

            # 生成稳定 hash 并去重。
            source_hash = compute_source_hash(text, source_path, page)
            if source_hash in seen_hashes:
                continue
            seen_hashes.add(source_hash)

            # 组装 chunk 元数据（继承 document 元数据 + 位置信息）。
            meta = dict(doc.metadata)
            meta.update(
                {
                    "chunk_index": len(chunks),
                    "char_start": char_start,
                    "char_end": char_end,
                    "source_hash": source_hash,
                    "is_question_title": is_question_title,
                }
            )
            chunks.append(
                Chunk(chunk_id=f"CH-{source_hash}", text=text, metadata=meta)
            )

        # 处理剩余的过短缓冲：作为一个块保留（若非空）。
        if pending_short and len(pending_short) >= min_chunk_chars // 2:
            source_hash = compute_source_hash(pending_short, source_path, page)
            if source_hash not in seen_hashes:
                seen_hashes.add(source_hash)
                meta = dict(doc.metadata)
                meta.update(
                    {
                        "chunk_index": len(chunks),
                        "char_start": char_cursor,
                        "char_end": char_cursor + len(pending_short),
                        "source_hash": source_hash,
                        "is_question_title": False,
                    }
                )
                chunks.append(
                    Chunk(chunk_id=f"CH-{source_hash}", text=pending_short, metadata=meta)
                )

    logger.info("chunk_documents：输入 %d 文档 -> %d chunks", len(documents), len(chunks))
    return chunks
