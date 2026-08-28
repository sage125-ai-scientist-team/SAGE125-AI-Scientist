"""
app.clients.literature_clients —— 学术文献检索客户端集合。

封装三个开放文献 API，用于生成**可溯源**的 EvidenceCard 候选：
    - ArxivClient    : arXiv 预印本检索（无需 Key，遵守请求间隔限流，不下载 PDF 全文）。
    - OpenAlexClient : OpenAlex 学术图谱检索（无 Key 则跳过，不报错；带 api_key/mailto）。
    - CrossrefClient : Crossref DOI/标题/期刊/年份核验（无需 Key，带 mailto）。

反造假约束：
    所有返回的 DOI / URL / 作者 / 期刊 / 年份必须来自 API 真实响应，
    严禁本地拼造或补全不存在的元数据。
"""

from __future__ import annotations

import re
import time
from typing import Mapping, Optional

from app.core.config import Settings, get_settings
from app.core.logging import get_logger, mask_text
from app.core.schemas import EvidenceCard

# 模块级日志器。
logger = get_logger("clients.literature")

# 文献候选的默认相关性分数（未经原文打分前的中性占位，检索器会覆盖）。
_DEFAULT_RELEVANCE = 0.5
_JATS_TAG = re.compile(r"<[^>]+>")


def reconstruct_openalex_abstract(inverted: Mapping[str, object] | None) -> str:
    """把 OpenAlex `abstract_inverted_index` 还原成摘要原文，不补造缺失词。"""
    if not isinstance(inverted, Mapping) or not inverted:
        return ""
    placed: list[tuple[int, str]] = []
    max_pos = -1
    for word, indexes in inverted.items():
        token = str(word or "").strip()
        if not token or not isinstance(indexes, list):
            continue
        for raw_index in indexes:
            try:
                position = int(raw_index)
            except (TypeError, ValueError):
                continue
            if position < 0:
                continue
            placed.append((position, token))
            if position > max_pos:
                max_pos = position
    if max_pos < 0:
        return ""
    slots = [""] * (max_pos + 1)
    for position, token in placed:
        slots[position] = token
    return " ".join(token for token in slots if token).strip()


def _plain_abstract(raw: object) -> str:
    """去掉 Crossref JATS 标签，只保留接口返回的摘要文本。"""
    text = _JATS_TAG.sub(" ", str(raw or ""))
    return " ".join(text.split())


class ArxivClient:
    """arXiv 预印本检索客户端（遵守请求间隔以尊重服务方限流，不下载全文）。"""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        """
        初始化 arXiv 客户端。

        参数：
            settings: 可选注入配置；缺省使用全局单例。
        """
        # 允许注入配置以便测试。
        self.settings = settings or get_settings()
        # 记录上次请求时间戳，用于强制请求间隔。
        self._last_request_ts = 0.0

    def _respect_rate_limit(self) -> None:
        """
        根据 ARXIV_REQUEST_INTERVAL_SECONDS 强制两次请求之间的最小间隔。

        返回：
            None（必要时通过 sleep 阻塞至满足间隔）。
        """
        # 计算距上次请求已过去的时间。
        interval = float(self.settings.arxiv_request_interval_seconds or 3.0)
        elapsed = time.time() - self._last_request_ts
        # 不足间隔则补足 sleep（默认至少 3 秒）。
        if elapsed < interval:
            time.sleep(interval - elapsed)

    def search(self, query: str, max_results: int = 10) -> list[EvidenceCard]:
        """
        检索 arXiv 并返回可溯源的证据候选。

        参数：
            query:       检索关键词。
            max_results: 最大返回条数。

        返回：
            EvidenceCard 列表（source_type="arxiv"）；失败时返回空列表并记日志。
        """
        # 先遵守限流。
        self._respect_rate_limit()

        # 延迟导入依赖，避免测试环境强依赖。
        try:
            import requests
            import feedparser
        except ImportError:
            logger.warning("未安装 requests/feedparser，arXiv 检索跳过。")
            return []

        # 组装 arXiv Atom API 查询参数。
        params = {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": max_results,
        }
        try:
            resp = requests.get(self.settings.arxiv_base_url, params=params, timeout=30)
            # 更新最近请求时间戳。
            self._last_request_ts = time.time()
            resp.raise_for_status()
        except Exception as exc:
            # 失败不报错中断，仅记日志并返回空。
            logger.warning("arXiv 检索失败：%s", mask_text(str(exc)))
            return []

        # 用 feedparser 解析 Atom 响应。
        feed = feedparser.parse(resp.text)
        cards: list[EvidenceCard] = []
        for entry in feed.entries:
            # 提取年份（从 published 的前 4 位）。
            year = None
            published = getattr(entry, "published", "")
            if published[:4].isdigit():
                year = int(published[:4])
            # 组装证据卡片，均来自真实响应字段。
            cards.append(
                EvidenceCard(
                    id=getattr(entry, "id", "") or f"arxiv:{query}",
                    source_type="arxiv",
                    title=getattr(entry, "title", "").strip(),
                    authors=[a.get("name", "") for a in getattr(entry, "authors", [])],
                    year=year,
                    url=getattr(entry, "link", None),
                    doi=getattr(entry, "arxiv_doi", None),
                    # 仅使用摘要片段，不下载 PDF 全文。
                    quoted_text=getattr(entry, "summary", "").strip()[:500],
                    summary=getattr(entry, "summary", "").strip()[:500],
                    relevance_score=_DEFAULT_RELEVANCE,
                    reliability_note="arxiv_preprint_not_peer_reviewed",
                )
            )
        return cards


class OpenAlexClient:
    """OpenAlex 学术图谱检索客户端（无 Key 则优雅跳过）。"""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        """
        初始化 OpenAlex 客户端。

        参数：
            settings: 可选注入配置；缺省使用全局单例。
        """
        # 允许注入配置以便测试。
        self.settings = settings or get_settings()

    def search(self, query: str, per_page: int = 10) -> list[EvidenceCard]:
        """
        检索 OpenAlex 并返回可溯源证据候选。

        参数：
            query:    检索关键词。
            per_page: 每页返回条数。

        返回：
            EvidenceCard 列表（source_type="openalex"）；未配置 Key 时返回空列表（不报错）。
        """
        # 未配置 OPENALEX_API_KEY 则跳过（可选能力），不报错。
        if not self.settings.openalex_configured:
            logger.info("未配置 OPENALEX_API_KEY，OpenAlex 检索跳过（可选能力）。")
            return []

        try:
            import requests
        except ImportError:
            logger.warning("未安装 requests，OpenAlex 检索跳过。")
            return []

        # 组装查询参数：api_key 作为 query parameter，并带 mailto 进入 polite pool。
        params = {
            "search": query,
            "per-page": per_page,
            "api_key": self.settings.openalex_api_key,
        }
        if self.settings.contact_email:
            params["mailto"] = self.settings.contact_email

        try:
            resp = requests.get("https://api.openalex.org/works", params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("OpenAlex 检索失败：%s", mask_text(str(exc)))
            return []

        cards: list[EvidenceCard] = []
        for work in data.get("results", []):
            # 作者列表从 authorships 提取（真实字段）。
            authors = [
                a.get("author", {}).get("display_name", "")
                for a in work.get("authorships", [])
            ]
            title = work.get("title") or ""
            abstract = reconstruct_openalex_abstract(work.get("abstract_inverted_index"))
            snippet = (abstract or title).strip()
            cards.append(
                EvidenceCard(
                    id=work.get("id", f"openalex:{query}"),
                    source_type="openalex",
                    title=title,
                    authors=[a for a in authors if a],
                    year=work.get("publication_year"),
                    url=work.get("id"),
                    doi=(work.get("doi") or "").replace("https://doi.org/", "") or None,
                    quoted_text=snippet[:800],
                    summary=(abstract[:180] if abstract else title),
                    relevance_score=_DEFAULT_RELEVANCE,
                    reliability_note=(
                        "openalex_abstract" if abstract else "openalex_metadata"
                    ),
                )
            )
        return cards


class CrossrefClient:
    """Crossref DOI/标题/期刊/年份核验客户端（无需 Key，带 mailto）。"""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        """
        初始化 Crossref 客户端。

        参数：
            settings: 可选注入配置；缺省使用全局单例。
        """
        # 允许注入配置以便测试。
        self.settings = settings or get_settings()
        # CONTACT_EMAIL 为空仍可运行，但记日志建议配置以进入 polite pool。
        if not self.settings.contact_email:
            logger.info("未配置 CONTACT_EMAIL，Crossref 仍可运行，但建议配置以进入 polite pool。")

    def search(self, query: str, rows: int = 10) -> list[EvidenceCard]:
        """
        检索 Crossref 并返回可溯源证据候选（可用于 DOI/期刊/年份核验）。

        参数：
            query: 检索关键词。
            rows:  返回条数。

        返回：
            EvidenceCard 列表（source_type="crossref"）；失败时返回空列表并记日志。
        """
        try:
            import requests
        except ImportError:
            logger.warning("未安装 requests，Crossref 检索跳过。")
            return []

        # 组装查询参数，带 mailto（若配置）以进入 polite pool。
        params: dict = {"query": query, "rows": rows}
        if self.settings.contact_email:
            params["mailto"] = self.settings.contact_email

        try:
            resp = requests.get(
                f"{self.settings.crossref_base_url}/works", params=params, timeout=30
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("Crossref 检索失败：%s", mask_text(str(exc)))
            return []

        cards: list[EvidenceCard] = []
        for item in data.get("message", {}).get("items", []):
            # 标题为数组，取首个。
            title_list = item.get("title") or [""]
            title = title_list[0] if title_list else ""
            # 作者：拼接 given + family。
            authors = [
                f"{a.get('given', '')} {a.get('family', '')}".strip()
                for a in item.get("author", [])
            ]
            # 年份从 issued.date-parts 提取。
            year = None
            date_parts = item.get("issued", {}).get("date-parts", [[None]])
            if date_parts and date_parts[0] and date_parts[0][0]:
                year = date_parts[0][0]
            # 期刊名（container-title）作为可靠性说明的一部分。
            container = (item.get("container-title") or [""])
            journal = container[0] if container else ""
            abstract = _plain_abstract(item.get("abstract"))
            snippet = abstract or title
            note = "crossref_abstract" if abstract else "crossref_metadata"
            summary = abstract[:180] if abstract else (
                f"{title}（{journal}）" if journal else title
            )
            cards.append(
                EvidenceCard(
                    id=item.get("DOI", f"crossref:{query}"),
                    source_type="crossref",
                    title=title,
                    authors=[a for a in authors if a],
                    year=year,
                    url=item.get("URL"),
                    doi=item.get("DOI"),
                    quoted_text=snippet[:800],
                    summary=summary,
                    relevance_score=_DEFAULT_RELEVANCE,
                    reliability_note=note,
                )
            )
        return cards
