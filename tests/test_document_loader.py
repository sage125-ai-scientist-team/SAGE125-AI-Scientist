"""
tests/test_document_loader.py — 文档加载器测试。

覆盖：
    - TXT / MD / CSV loader 可运行且 metadata 完整；
    - PDF 不存在时报清晰错误；
    - 不支持的类型抛 UnsupportedFileTypeError。
"""

from __future__ import annotations

import pytest

from app.rag.document_loader import (
    UnsupportedFileTypeError,
    load_any,
    load_csv,
    load_md,
    load_pdf,
    load_txt,
)

# metadata 必须包含的键。
_REQUIRED_META = {"source_path", "source_name", "file_type", "page", "doc_id", "created_at", "is_user_upload"}


def test_load_txt(tmp_path):
    """TXT 加载应返回 Document 且 metadata 完整。"""
    f = tmp_path / "a.txt"
    f.write_text("hello world", encoding="utf-8")
    docs = load_txt(str(f))
    assert len(docs) == 1
    assert docs[0].text == "hello world"
    assert _REQUIRED_META.issubset(docs[0].metadata.keys())
    assert docs[0].metadata["file_type"] == "txt"


def test_load_md(tmp_path):
    """MD 加载应保留标题层级。"""
    f = tmp_path / "a.md"
    f.write_text("# Title\n\ncontent", encoding="utf-8")
    docs = load_md(str(f))
    assert "# Title" in docs[0].text
    assert docs[0].metadata["file_type"] == "md"


def test_load_csv(tmp_path):
    """CSV 加载应包含列名并记录 row_range。"""
    f = tmp_path / "a.csv"
    f.write_text("name,value\nfoo,1\nbar,2\n", encoding="utf-8")
    docs = load_csv(str(f))
    assert len(docs) >= 1
    assert "name" in docs[0].text
    assert docs[0].metadata["file_type"] == "csv"
    assert "row_range" in docs[0].metadata


def test_load_pdf_missing_raises():
    """PDF 不存在时应抛出 FileNotFoundError。"""
    with pytest.raises(FileNotFoundError):
        load_pdf("does_not_exist_12345.pdf")


def test_load_any_unsupported(tmp_path):
    """不支持的扩展名应抛 UnsupportedFileTypeError。"""
    f = tmp_path / "a.docx"
    f.write_text("x", encoding="utf-8")
    with pytest.raises(UnsupportedFileTypeError):
        load_any(str(f))
