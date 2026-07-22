"""用户文献库文档必须如实说明持久化、配额、删除与外发边界。"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_readme_documents_user_library_lifecycle_and_scope():
    text = _read(ROOT / "README.md")

    assert "sjtu-booklet.pdf" in text
    assert "永不作为 Local RAG 的本地文献证据" in text
    assert "永久保存在本机文献库" in text
    assert "后续不同问题中复用" in text
    assert "单文件 25 MiB" in text
    assert "单批最多 10 个文件且合计 100 MiB" in text
    assert "DELETE /library/documents/{document_id}" in text


def test_user_guide_discloses_bailian_embedding_data_flow():
    text = _read(ROOT / "docs" / "USER_GUIDE.md")

    assert "切分后的文本片段发送到阿里云百炼 embedding 接口" in text
    assert "不会上传到 arXiv、OpenAlex 或 Crossref" in text
    assert "同一内容即使文件名不同也只保存、索引一次" in text
    assert "历史快照" in text

