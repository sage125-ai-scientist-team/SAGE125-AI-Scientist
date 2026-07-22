#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
scripts/build_rag_index.py — 构建本地 RAG 向量索引。

流程：
    DocumentLoader -> Chunker -> EmbeddingClient -> 向量库(zvec) -> persist，
    并输出 manifest / build_report / chunks.jsonl / zvec_capabilities.json。

命令行参数：
    --input           输入目录（默认 data/raw）
    --index-dir       索引目录（默认 data/index）
    --include-uploads 一并索引 data/raw/uploads 下的用户文件
    --force-rebuild   忽略 hash 去重，强制重建
    --mock-embedding  使用确定性 mock 嵌入（仅测试，不可用于正式评审）

安全：
    - 缺少 sjtu-booklet.pdf / DASHSCOPE_API_KEY / zvec 时给出清晰提示；
    - 任何外部 API 失败不静默，给出明确错误。
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

# 确保项目根在 sys.path 中。
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.rag.chunker import chunk_documents
from app.rag.document_loader import Document, load_any
from app.rag.indexing_service import mock_embed
from app.rag.zvec_store import get_vector_store, inspect_zvec_capabilities

# 模块级日志器。
logger = get_logger("scripts.build_rag_index")

# 项目根目录。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
# booklet PDF 默认路径。
BOOKLET_PDF = PROJECT_ROOT / "data" / "raw" / "sjtu-booklet.pdf"


def _supported_files(input_dir: Path, include_uploads: bool) -> list[Path]:
    """
    收集待索引文件（booklet PDF + 可选 uploads 下的 pdf/txt/md/csv）。

    参数：
        input_dir:       输入目录。
        include_uploads: 是否包含 uploads 子目录。

    返回：
        文件路径列表。
    """
    exts = {".pdf", ".txt", ".md", ".csv"}
    files: list[Path] = []
    # 默认加载 input_dir 下的支持文件（非递归，避免误入 uploads 私密文件）。
    for p in sorted(input_dir.glob("*")):
        if p.is_file() and p.suffix.lower() in exts:
            files.append(p)
    # 可选：加载 uploads 子目录（用户上传）。
    if include_uploads:
        uploads = input_dir / "uploads"
        if uploads.exists():
            for p in sorted(uploads.rglob("*")):
                if p.is_file() and p.suffix.lower() in exts:
                    files.append(p)
    return files


def _embed(texts: list[str], mock: bool):
    """
    对文本执行嵌入（mock 或真实百炼）。

    参数：
        texts: 文本列表。
        mock:  是否使用确定性 mock 嵌入。

    返回：
        (向量列表, 使用的嵌入模型名)。
    """
    # mock：确定性向量。
    if mock:
        return mock_embed(texts), "mock-embedding"
    # 真实：百炼 text-embedding-v4。
    from app.clients.embedding_client import EmbeddingClient

    client = EmbeddingClient()
    return client.embed_texts(texts), get_settings().bailian_embedding_model


def main() -> int:
    """
    脚本主入口：解析参数 -> 前置检查 -> 构建索引 -> 写出 manifest/report。

    返回：
        进程退出码（前置检查失败返回非 0）。
    """
    # 解析命令行参数。
    parser = argparse.ArgumentParser(description="构建 SAGE125 本地 RAG 索引")
    parser.add_argument("--input", default=str(PROJECT_ROOT / "data" / "raw"))
    parser.add_argument("--index-dir", default=str(PROJECT_ROOT / "data" / "index"))
    parser.add_argument("--include-uploads", action="store_true")
    parser.add_argument("--force-rebuild", action="store_true")
    parser.add_argument("--mock-embedding", action="store_true")
    args = parser.parse_args()

    # 初始化日志。
    settings = get_settings()
    setup_logging(settings.log_level)

    input_dir = Path(args.input)
    index_root = Path(args.index_dir)
    zvec_dir = index_root / "zvec"

    # 前置检查 1：booklet PDF 存在。
    if not BOOKLET_PDF.exists():
        print("错误：请将 sjtu-booklet.pdf 放到 data/raw/sjtu-booklet.pdf")
        return 2

    # 前置检查 2：真实嵌入需要百炼配置。
    if not args.mock_embedding and not settings.qwen_configured:
        print("错误：DASHSCOPE_API_KEY 未配置。请先运行 python scripts/setup_env.py，")
        print("或使用 --mock-embedding 进行测试（mock 结果不可用于正式评审）。")
        return 3

    # 探测 zvec 能力并落盘（无论 mock 与否都记录）。
    caps = inspect_zvec_capabilities()
    use_mock_store = os.getenv("MOCK_VECTOR_STORE", "").strip().lower() in ("1", "true", "yes")
    # 前置检查 3：非 mock 向量库时需要 zvec 可用。
    if not use_mock_store and not caps.get("installed"):
        print("错误：zvec 不可用。请 pip install zvec，或设置 MOCK_VECTOR_STORE=true 使用内存向量库（测试用）。")
        return 4

    # 收集待索引文件。
    files = _supported_files(input_dir, args.include_uploads)
    if not files:
        print(f"错误：{input_dir} 下未找到可索引文件（pdf/txt/md/csv）。")
        return 5

    logger.info("开始构建索引：files=%d，mock_embedding=%s", len(files), args.mock_embedding)

    # 加载 + 切分。
    documents: list[Document] = []
    source_files: list[str] = []
    for f in files:
        # uploads 目录内的文件标记为用户上传。
        is_upload = "uploads" in f.parts
        try:
            documents.extend(load_any(str(f), is_user_upload=is_upload))
            source_files.append(f.name)
        except Exception as exc:
            # 不静默：明确报错并继续其它文件。
            print(f"警告：加载失败 {f.name}: {exc}")

    if not documents:
        print("错误：没有成功加载任何文档。")
        return 6

    chunks = chunk_documents(documents)
    if not chunks:
        print("错误：切分后没有得到任何 chunk。")
        return 7

    # 嵌入。
    try:
        embeddings, embedding_model = _embed([c.text for c in chunks], args.mock_embedding)
    except Exception as exc:
        # 外部 API 失败不静默。
        print(f"错误：嵌入失败：{exc}")
        return 8

    vector_dimension = len(embeddings[0]) if embeddings else 0

    # force-rebuild 时清除旧 zvec 目录，避免 mock/real 嵌入维度不一致。
    if args.force_rebuild and zvec_dir.exists():
        shutil.rmtree(zvec_dir)

    # 写入向量库并持久化。
    try:
        store = get_vector_store(dimension=vector_dimension, index_dir=str(zvec_dir))
        store.add_documents(chunks, embeddings)
        store.persist()
    except Exception as exc:
        print(f"错误：写入向量库失败：{exc}")
        return 9

    # 组装 manifest。
    index_root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_files": source_files,
        "file_count": len(source_files),
        "document_count": len(documents),
        "chunk_count": len(chunks),
        "embedding_model": embedding_model,
        "rerank_model": settings.bailian_rerank_model,
        "vector_dimension": vector_dimension,
        "vector_store": "memory" if use_mock_store else "zvec",
        "index_dir": str(zvec_dir),
        "source_hashes": [c.metadata.get("source_hash") for c in chunks],
        "mock_embedding": bool(args.mock_embedding),
    }
    (index_root / "index_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 写 build_report.md。
    report_lines = [
        "# RAG 索引构建报告\n",
        f"- 生成时间（UTC）：{manifest['created_at']}",
        f"- 文件数：{manifest['file_count']}",
        f"- 文档（页/行）数：{manifest['document_count']}",
        f"- chunk 数：{manifest['chunk_count']}",
        f"- 向量维度：{manifest['vector_dimension']}",
        f"- 向量库：{manifest['vector_store']}",
        f"- 嵌入模型：{manifest['embedding_model']}",
        f"- 索引目录：{manifest['index_dir']}",
        f"- mock_embedding：{manifest['mock_embedding']}",
        "",
    ]
    if args.mock_embedding:
        report_lines.append("> 注意：本索引使用 mock embedding，仅用于测试，**不可用于正式评审结果**。")
    (index_root / "build_report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    # 控制台输出汇总。
    print("=" * 56)
    print("RAG 索引构建完成")
    print(f"  文件数        : {manifest['file_count']}")
    print(f"  文档(页/行)数 : {manifest['document_count']}")
    print(f"  chunk 数      : {manifest['chunk_count']}")
    print(f"  向量维度      : {manifest['vector_dimension']}")
    print(f"  向量库        : {manifest['vector_store']}")
    print(f"  索引目录      : {manifest['index_dir']}")
    print(f"  mock_embedding: {manifest['mock_embedding']}")
    print("=" * 56)
    return 0


if __name__ == "__main__":
    sys.exit(main())
