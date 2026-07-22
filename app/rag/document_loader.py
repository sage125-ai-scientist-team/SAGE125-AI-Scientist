"""
app.rag.document_loader —— 原始文档加载器。

将 PDF / TXT / MD / CSV 加载为统一的 Document 结构，供 chunker 切分与索引。
每个 Document 携带完整来源元数据，保证后续证据可追溯、可复现。

安全要求：
    - 用户上传文件仅用于本地索引，绝不上传到 arXiv/OpenAlex/Crossref；
    - 日志不打印用户文件全文，仅记录文件名、页/行数、chunk 数等非敏感信息。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.logging import get_logger

# 模块级日志器。
logger = get_logger("rag.document_loader")

# 支持的文件扩展名到 file_type 的映射。
_SUPPORTED_EXTENSIONS = {".pdf": "pdf", ".txt": "txt", ".md": "md", ".csv": "csv"}

# CSV 分批转文本时，每个 Document 承载的最大行数，避免超大文本。
_CSV_ROWS_PER_DOC = 50


class UnsupportedFileTypeError(Exception):
    """当尝试加载不受支持的文件类型时抛出。"""


@dataclass
class Document:
    """
    统一文档单元：一段文本 + 来源元数据。

    metadata 至少包含：source_path / source_name / file_type / page /
    doc_id / created_at / is_user_upload。
    """

    # 文本内容。
    text: str
    # 来源元数据。
    metadata: dict[str, Any] = field(default_factory=dict)


def _base_metadata(path: Path, file_type: str, is_user_upload: bool) -> dict[str, Any]:
    """
    构造 Document 的基础元数据（不含 page，由各 loader 补充）。

    参数：
        path:           文件路径。
        file_type:      文件类型（pdf/txt/md/csv）。
        is_user_upload: 是否为用户上传文件。

    返回：
        基础元数据字典。
    """
    # doc_id 用于追溯同一源文件的所有片段。
    return {
        "source_path": str(path),
        "source_name": path.name,
        "file_type": file_type,
        "doc_id": uuid.uuid5(uuid.NAMESPACE_URL, str(path)).hex,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "is_user_upload": is_user_upload,
    }


def load_pdf(path: str, is_user_upload: bool = False) -> list[Document]:
    """
    使用 PyMuPDF 按页加载 PDF（不做 OCR，跳过空页）。

    参数：
        path:           PDF 文件路径。
        is_user_upload: 是否用户上传。

    返回：
        Document 列表，每页一个；metadata.page 为 1-based 页码。

    异常：
        FileNotFoundError: 文件不存在时抛出。
        RuntimeError:      PyMuPDF 不可用时抛出。
    """
    p = Path(path)
    # 文件存在性检查。
    if not p.exists():
        raise FileNotFoundError(f"PDF 文件不存在：{path}")
    # 延迟导入 PyMuPDF。
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("未安装 PyMuPDF，请先 pip install pymupdf。") from exc

    docs: list[Document] = []
    doc = fitz.open(str(p))
    for pno in range(doc.page_count):
        # 使用 sort=True 缓解多栏顺序错乱。
        text = doc[pno].get_text("text", sort=True).strip()
        # 跳过空页。
        if not text:
            continue
        meta = _base_metadata(p, "pdf", is_user_upload)
        # 1-based 页码，便于前端展示。
        meta["page"] = pno + 1
        docs.append(Document(text=text, metadata=meta))
    doc.close()
    # 仅记录非敏感统计信息。
    logger.info("load_pdf：%s，页数=%d", p.name, len(docs))
    return docs


def load_txt(path: str, is_user_upload: bool = False) -> list[Document]:
    """
    加载纯文本文件，自动尝试 utf-8 / utf-8-sig / gbk 编码。

    参数：
        path:           文本文件路径。
        is_user_upload: 是否用户上传。

    返回：
        含单个 Document 的列表；metadata.page = 1。

    异常：
        FileNotFoundError: 文件不存在时抛出。
        UnicodeError:      所有编码尝试失败时抛出（清晰报错）。
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"文本文件不存在：{path}")
    # 依次尝试常见编码。
    text = None
    for enc in ("utf-8", "utf-8-sig", "gbk"):
        try:
            text = p.read_text(encoding=enc)
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    # 全部失败则清晰报错。
    if text is None:
        raise UnicodeError(f"无法解码文本文件（尝试 utf-8/utf-8-sig/gbk 均失败）：{path}")
    meta = _base_metadata(p, "txt", is_user_upload)
    meta["page"] = 1
    logger.info("load_txt：%s，chars=%d", p.name, len(text))
    return [Document(text=text, metadata=meta)]


def load_md(path: str, is_user_upload: bool = False) -> list[Document]:
    """
    加载 Markdown 文件，保留标题层级（原样保留 # 标记）。

    参数：
        path:           Markdown 文件路径。
        is_user_upload: 是否用户上传。

    返回：
        含单个 Document 的列表；metadata.page = 1、file_type = "md"。

    异常：
        FileNotFoundError: 文件不存在时抛出。
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Markdown 文件不存在：{path}")
    # Markdown 直接按 utf-8 读取，保留标题符号。
    text = p.read_text(encoding="utf-8")
    meta = _base_metadata(p, "md", is_user_upload)
    meta["page"] = 1
    logger.info("load_md：%s，chars=%d", p.name, len(text))
    return [Document(text=text, metadata=meta)]


def load_csv(path: str, is_user_upload: bool = False) -> list[Document]:
    """
    使用 pandas 加载 CSV，按行分批转为带列名的文本 Document。

    参数：
        path:           CSV 文件路径。
        is_user_upload: 是否用户上传。

    返回：
        Document 列表；每个 Document 承载若干行，metadata.row_range 记录行范围。

    异常：
        FileNotFoundError: 文件不存在时抛出。
        RuntimeError:      pandas 不可用时抛出。
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"CSV 文件不存在：{path}")
    # 延迟导入 pandas。
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("未安装 pandas，请先 pip install pandas。") from exc

    df = pd.read_csv(p)
    columns = list(df.columns)
    docs: list[Document] = []
    # 分批，避免把大型 CSV 拼成超大文本。
    for start in range(0, len(df), _CSV_ROWS_PER_DOC):
        chunk_df = df.iloc[start : start + _CSV_ROWS_PER_DOC]
        # 每行转为 "列名: 值" 组合，包含列名以保留语义。
        rows_text = []
        for _, row in chunk_df.iterrows():
            rows_text.append("; ".join(f"{col}: {row[col]}" for col in columns))
        text = "\n".join(rows_text)
        meta = _base_metadata(p, "csv", is_user_upload)
        meta["page"] = 1
        # 记录行范围（1-based，闭区间）。
        meta["row_range"] = [start + 1, min(start + _CSV_ROWS_PER_DOC, len(df))]
        docs.append(Document(text=text, metadata=meta))
    logger.info("load_csv：%s，rows=%d，docs=%d", p.name, len(df), len(docs))
    return docs


def load_any(path: str, is_user_upload: bool = False) -> list[Document]:
    """
    按扩展名分发到相应 loader（支持 pdf/txt/md/csv）。

    参数：
        path:           文件路径。
        is_user_upload: 是否用户上传。

    返回：
        Document 列表。

    异常：
        UnsupportedFileTypeError: 不支持的扩展名。
    """
    ext = Path(path).suffix.lower()
    file_type = _SUPPORTED_EXTENSIONS.get(ext)
    # 不支持的类型明确报错。
    if file_type is None:
        raise UnsupportedFileTypeError(
            f"不支持的文件类型：{ext}（仅支持 pdf/txt/md/csv）。"
        )
    # 分发到对应 loader。
    if file_type == "pdf":
        return load_pdf(path, is_user_upload)
    if file_type == "txt":
        return load_txt(path, is_user_upload)
    if file_type == "md":
        return load_md(path, is_user_upload)
    return load_csv(path, is_user_upload)
