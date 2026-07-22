#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
scripts/extract_125_questions.py — 从 booklet PDF 稳定抽取 125 个科学问题。

输入：
    data/raw/sjtu-booklet.pdf（《125 Questions: Exploration and Discovery》）

输出：
    data/processed/questions_125.json
    data/processed/questions_125.csv
    data/processed/extraction_report.md

抽取原理（经 PDF 结构实测得出，稳健且可复现）：
    该 booklet 采用固定排版，可用字体样式区分内容层级：
        - 领域标题：字体 MyriadPro-Bold，字号 >= 16（如 "Medicine & Health"）；
        - 问题标题：字体 MyriadPro-Bold，字号约 12（可跨行，末尾以 ? 结束）；
        - 解释正文：字体 AvenirNext-*，字号约 9。
    同时 booklet 为**双栏排版**，故先按“列（x 坐标）→ 纵向 y”重建阅读顺序，
    避免多栏交错导致领域与问题错配（正文页 7、25、29 等存在跨领域情况）。

反造假：
    仅抽取 PDF 中真实存在的问题与原文摘录，excerpt 不由模型改写。
"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# 确保项目根在 sys.path 中，使脚本可直接 `python scripts/xxx.py` 运行并导入 app 包。
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.logging import get_logger

# 模块级日志器（继承脱敏能力）。
logger = get_logger("scripts.extract_questions")

# 项目根目录：本文件位于 <root>/scripts/。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
# 输入 PDF 路径。
PDF_PATH = PROJECT_ROOT / "data" / "raw" / "sjtu-booklet.pdf"
# 输出目录与文件。
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
JSON_PATH = PROCESSED_DIR / "questions_125.json"
CSV_PATH = PROCESSED_DIR / "questions_125.csv"
REPORT_PATH = PROCESSED_DIR / "extraction_report.md"

# 12 个标准领域（用于领域标题匹配与校验）。
STANDARD_DOMAINS = [
    "Mathematical Sciences",
    "Chemistry",
    "Medicine & Health",
    "Biology",
    "Astronomy",
    "Physics",
    "Engineering & Materials Science",
    "Information Science",
    "Neuroscience",
    "Ecology",
    "Energy Science",
    "Artificial Intelligence",
]

# 目标题量：本 booklet 恰好 125 个问题。
TARGET_COUNT = 125

# 根据 booklet 中 12 个领域标题的源页面分组得到的预期分布。
# 该约束可捕捉“总数仍为 125，但某题被分到相邻领域”的错误。
EXPECTED_DOMAIN_COUNTS = {
    "Mathematical Sciences": 3,
    "Chemistry": 9,
    "Medicine & Health": 10,
    "Biology": 23,
    "Astronomy": 23,
    "Physics": 18,
    "Engineering & Materials Science": 4,
    "Information Science": 4,
    "Neuroscience": 12,
    "Ecology": 8,
    "Energy Science": 3,
    "Artificial Intelligence": 8,
}

# 关键 demo 问题：必须能被识别（否则触发 fallback 补入）。
PANDEMIC_QUESTION = "Can we predict the next pandemic?"

# 固定版式中经人工与源 PDF 逐字核对的跨栏校正项。
#
# 这些文本不是模型生成的改写，而是 booklet 对应页面的原文。PyMuPDF 在
# 第 12/41/42 页会把左右栏同一水平位置的行交错返回，因此需要在结构抽取
# 后做一层可重复的源文校正，同时保持既有 Q 编号稳定。
_CANONICAL_LAYOUT_ITEMS = {
    "riemann": {
        "question": "Is the Riemann hypothesis true?",
        "domain": "Mathematical Sciences",
        "source_page": 7,
    },
    "vaccines": {
        "question": "How will the next generation of vaccines be made?",
        "domain": "Medicine & Health",
        "source_page": 12,
        "booklet_excerpt": (
            "Next-generation vaccine platforms accelerate vaccine development by sequencing viral proteins. "
            "Today we are seeing viral vector vaccines, nucleic acid–based vaccines, and antigen-presenting "
            "cells being leveraged to fight COVID-19."
        ),
    },
    "meridian": {
        "question": "Is there a scientific basis to the Meridian System in traditional Chinese medicine?",
        "domain": "Medicine & Health",
        "source_page": 12,
        "booklet_excerpt": (
            "Traditional Chinese medicine contends that energy flows through the body by way of 12 main "
            "channels called meridians, which correlate with organs. Various diseases are associated with "
            "blocked meridians, and acupuncture stimulates points on the body, releasing and easing the energy "
            "flow. There have been many scientific examinations exploring the Meridian System and the use of "
            "acupuncture for treatment of disorders, and some studies suggest that acupuncture may help ease "
            "chronic pain and prevent migraine headaches. Other investigations suggest that acupuncture impacts "
            "the way the brain processes pain, according to the U.S. National Institutes of Health."
        ),
    },
    "ai_replace": {
        "question": "Will artificial intelligence replace humans?",
        "domain": "Artificial Intelligence",
        "source_page": 41,
        "booklet_excerpt": (
            "While AI can perform tasks at speeds beyond human ability, its power is limited by its inability "
            "to use intuitive, holistic approaches to deal with uncertainty and equivocality problems."
        ),
    },
    "hybrid": {
        "question": "Could we integrate with computers to form a human–machine hybrid species?",
        "domain": "Artificial Intelligence",
        "source_page": 42,
        "booklet_excerpt": (
            "We are on the cusp of human–machine hybrids, especially given advancements in smart exoskeletons "
            "and prosthetics, implantable sensors and chips, AI, and genomic editing technologies."
        ),
    },
    "quantum_brain": {
        "question": "Can quantum artificial intelligence imitate the human brain?",
        "domain": "Artificial Intelligence",
        "source_page": 42,
        "booklet_excerpt": (
            "Moreover, the majority of artificial neural networks differ considerably from brains. For example, "
            "they rely on mathematical tricks beyond the reach of most biological systems. But there is one "
            "intriguing similarity between our brains and AI models: Researchers are still baffled as to why they "
            "work as well as they do! There is growing interest in the possibility that quantum effects may play "
            "a role in consciousness and information processing, but evidence is still limited. With more "
            "research, we may see even greater understanding of the brain through the application of quantum AI."
        ),
    },
}

# 合法疑问句的常见首词；用于识别“the human brain?”这类残句。
_QUESTION_STARTERS = (
    "What",
    "Why",
    "How",
    "When",
    "Where",
    "Who",
    "Which",
    "Will",
    "Would",
    "Can",
    "Could",
    "Should",
    "Are",
    "Is",
    "Do",
    "Does",
    "Did",
    "Have",
    "Has",
    "Was",
    "Were",
)

# 页眉文本（用于 normalize_text 兜底清理）。
_HEADER_PATTERNS = [
    "125 QUESTIONS: EXPLORATION AND DISCOVERY",
    "125 QUESTIONS",
]


def normalize_text(text: str) -> str:
    """
    清洗 PDF 抽取文本：修复 mojibake、去页眉页码、合并断行、修复连字符换行。

    参数：
        text: 原始抽取文本（可能含替换字符、软连字符、页眉、断行）。

    返回：
        清洗后的可读文本；尽量保留科学术语中的连字符（如 Navier-Stokes）。
    """
    # 修复常见 mojibake：en/em-dash 被解码为 "\ufffdC"（如 Navier–Stokes）→ 连字符。
    text = text.replace("\ufffdC", "-")
    # 去除不可见 / 空字符 / 软连字符。
    for ch in ("\u0000", "\u00ad", "\u200b", "\ufeff"):
        text = text.replace(ch, "")
    # 剩余替换字符（多为弯引号/撇号）统一去除，保证问号与术语符号不受影响。
    text = text.replace("\ufffd", "")
    # 去除页眉行。
    for pat in _HEADER_PATTERNS:
        text = text.replace(pat, " ")
    # 修复连字符换行：形如 "word-\nword" 且续行小写 → 合并为一个单词。
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    # 其余换行合并为空格。
    text = text.replace("\n", " ")
    # 去除独立页码（前后为空白的纯数字）。
    text = re.sub(r"\s+\d{1,3}\s+", " ", text)
    # 归一化多余空白。
    text = re.sub(r"\s+", " ", text).strip()
    return text


def match_domain(text: str) -> str | None:
    """
    将一行文本匹配到 12 个标准领域之一（允许大小写与空格差异）。

    参数：
        text: 候选领域标题文本。

    返回：
        命中的标准领域名；未命中返回 None。
    """
    # 归一化：去多余空白、转小写。
    norm = re.sub(r"\s+", " ", text).strip().lower()
    for domain in STANDARD_DOMAINS:
        if norm == domain.lower():
            return domain
    return None


def _iter_reading_order_lines(page):
    """
    以“列优先→纵向”的阅读顺序，产出页面每一行的样式信息。

    参数：
        page: PyMuPDF 页面对象。

    返回：
        列表，每项为 (size, font, text)，按双栏阅读顺序排列。
    """
    # 以页面中线划分左右栏。
    mid = page.rect.width / 2.0
    data = page.get_text("dict")
    lines: list[tuple[int, float, float, str, str]] = []
    for block in data.get("blocks", []):
        # 仅处理文本块（type==0）。
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            # 合并同一行的所有 span 文本。
            line_text = "".join(s.get("text", "") for s in spans).strip()
            if not line_text:
                continue
            x0, y0 = line["bbox"][0], line["bbox"][1]
            size = max((s.get("size", 0) for s in spans), default=0)
            font = spans[0].get("font", "") if spans else ""
            # 列号：左栏 0，右栏 1。
            col = 0 if x0 < mid else 1
            lines.append((col, round(y0, 1), size, font, line_text))
    # 列优先，再按纵向 y 排序，重建正确阅读顺序。
    lines.sort(key=lambda t: (t[0], t[1]))
    # 仅返回样式三元组。
    return [(size, font, text) for _col, _y, size, font, text in lines]


def _classify_line(size: float, font: str) -> str:
    """
    依据字号与字体，将一行分类为 domain / title / body / other。

    参数：
        size: 行的最大字号。
        font: 行首 span 的字体名。

    返回：
        分类标签之一："domain" / "title" / "body" / "other"。
    """
    # 领域标题：MyriadPro-Bold 且字号较大。
    if size >= 16 and "MyriadPro-Bold" in font:
        return "domain"
    # 问题标题：MyriadPro-Bold 且中等字号。
    if 11 <= size <= 14 and "MyriadPro-Bold" in font:
        return "title"
    # 解释正文：AvenirNext 字体族。
    if "AvenirNext" in font:
        return "body"
    # 其余（页眉、页码等）忽略。
    return "other"


def extract_raw_questions() -> list[dict]:
    """
    使用 PyMuPDF 按“字体样式 + 双栏阅读顺序”抽取问题及其正文摘录。

    返回：
        原始问题记录列表，每项含 question/domain/source_page/booklet_excerpt。
    异常：
        RuntimeError: 当 PyMuPDF 不可用时抛出。
    """
    # 延迟导入，给出清晰的安装提示。
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise RuntimeError("未安装 PyMuPDF，请先 pip install pymupdf。") from exc

    doc = fitz.open(str(PDF_PATH))
    # 构建跨页的全局阅读流：逐页、列优先，附带页码与分类。
    stream: list[tuple[int, str, float, str, str]] = []
    for pno in range(doc.page_count):
        for size, font, text in _iter_reading_order_lines(doc[pno]):
            stream.append((pno + 1, _classify_line(size, font), size, font, text))
    doc.close()

    questions: list[dict] = []
    current_domain: str | None = None
    title_buf: list[str] = []
    title_page: int | None = None
    # 当前正在收集 excerpt 的问题索引（-1 表示无）。
    collecting_idx = -1

    for page, kind, _size, _font, text in stream:
        if kind == "domain":
            # 命中领域标题则更新当前领域；未命中的大字号忽略。
            matched = match_domain(text)
            if matched:
                current_domain = matched
            # 领域切换终止上一个问题的 excerpt 收集与未完成标题。
            title_buf = []
            collecting_idx = -1
        elif kind == "title":
            # 新标题开始意味着上一个问题 excerpt 收集结束。
            collecting_idx = -1
            # 记录首行标题所在页码。
            if not title_buf:
                title_page = page
            title_buf.append(text)
            joined = normalize_text(" ".join(title_buf))
            # 标题以 ? 结束视为一个完整问题。
            if joined.endswith("?"):
                questions.append(
                    {
                        "question": joined,
                        "domain": current_domain or "Unknown",
                        "source_page": title_page,
                        "booklet_excerpt": "",
                    }
                )
                # 后续 body 文本归入该问题的 excerpt。
                collecting_idx = len(questions) - 1
                title_buf = []
        elif kind == "body":
            # 将解释正文追加到当前问题的 excerpt（跨页续接，直到遇到新标题/领域）。
            if collecting_idx >= 0:
                prev = questions[collecting_idx]["booklet_excerpt"]
                questions[collecting_idx]["booklet_excerpt"] = (prev + " " + text).strip()
        # other 行忽略。

    # 归一化并截断每个问题的 excerpt 到 300-800 字符范围。
    for q in questions:
        excerpt = normalize_text(q["booklet_excerpt"])
        # 上限 800 字符，尽量在句子边界截断。
        if len(excerpt) > 800:
            cut = excerpt[:800]
            last_period = cut.rfind(". ")
            excerpt = cut[: last_period + 1] if last_period > 300 else cut
        q["booklet_excerpt"] = excerpt
    return questions


def deduplicate_questions(candidates: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    对问题候选去重：完全重复与断行导致的近似重复。

    参数：
        candidates: 原始问题候选列表。

    返回：
        (去重后列表, 被去重列表)；以 normalized question 文本为 key。
    """
    seen: dict[str, dict] = {}
    unique: list[dict] = []
    removed: list[dict] = []
    for q in candidates:
        # 归一化 key：小写、去标点与多余空白，消除断行差异。
        key = re.sub(r"[^a-z0-9]+", " ", q["question"].lower()).strip()
        if key in seen:
            # 记录被去重项。
            removed.append(q)
            continue
        seen[key] = q
        unique.append(q)
    return unique, removed


def repair_known_layout_anomalies(questions: list[dict]) -> list[str]:
    """校正 booklet 固定双栏版式导致的已知跨栏错拼。

    校正以问题文本特征定位，而不依赖尚未分配的 Q 编号；因此重新运行抽取
    也会得到同样的结果。校正内容均来自源 PDF 第 7/12/41/42 页。

    参数：
        questions: 原始抽取记录（就地校正，必要时补入被粘连吞掉的第二题）。

    返回：
        已应用的校正标识列表，供报告审计。
    """

    repaired: list[str] = []

    def find_index(fragment: str, *, exclude: set[int] | None = None) -> int | None:
        blocked = exclude or set()
        fragment_lower = fragment.lower()
        for idx, item in enumerate(questions):
            if idx not in blocked and fragment_lower in str(item.get("question", "")).lower():
                return idx
        return None

    def apply(idx: int, key: str) -> None:
        canonical = _CANONICAL_LAYOUT_ITEMS[key]
        item = questions[idx]
        changed = False
        for field in ("question", "domain", "source_page", "booklet_excerpt"):
            if field in canonical and item.get(field) != canonical[field]:
                item[field] = canonical[field]
                changed = True
        if changed:
            item["_layout_repaired"] = True
            repaired.append(key)

    # 第 7 页：右栏的 Riemann 问题位于 Chemistry 标题之上，仍属于数学。
    riemann_idx = find_index("Riemann hypothesis")
    if riemann_idx is not None:
        apply(riemann_idx, "riemann")

    # 第 12 页：vaccine 与 Meridian 的两行标题被交错合并。
    vaccine_idx = find_index("next generation of vaccines")
    meridian_idx = find_index("System in traditional Chinese medicine", exclude={vaccine_idx} if vaccine_idx is not None else None)
    if vaccine_idx is not None:
        combined = "meridian" in str(questions[vaccine_idx].get("question", "")).lower()
        apply(vaccine_idx, "vaccines")
        if meridian_idx is None and combined:
            # 某些 PyMuPDF 版本会完全吞掉第二题，此时按源页面补回。
            meridian_idx = vaccine_idx + 1
            questions.insert(meridian_idx, dict(_CANONICAL_LAYOUT_ITEMS["meridian"], _layout_repaired=True))
            repaired.append("meridian")
    if meridian_idx is not None:
        apply(meridian_idx, "meridian")

    # 第 41 页：右栏的 nanobot 续文被追加到 AI replace humans 的摘录。
    replace_idx = find_index("artificial intelligence replace humans")
    if replace_idx is not None:
        apply(replace_idx, "ai_replace")

    # 第 42 页：human–machine hybrid 与 quantum AI 标题被交错合并。
    hybrid_idx = find_index("integrate with computers")
    quantum_idx = find_index("the human brain?", exclude={hybrid_idx} if hybrid_idx is not None else None)
    if hybrid_idx is not None:
        combined = "quantum artificial intelligence" in str(questions[hybrid_idx].get("question", "")).lower()
        apply(hybrid_idx, "hybrid")
        if quantum_idx is None and combined:
            quantum_idx = hybrid_idx + 1
            questions.insert(quantum_idx, dict(_CANONICAL_LAYOUT_ITEMS["quantum_brain"], _layout_repaired=True))
            repaired.append("quantum_brain")
    if quantum_idx is not None:
        apply(quantum_idx, "quantum_brain")

    return repaired


def validate_question_items(items: list[dict]) -> list[str]:
    """对最终 125 题执行数量、断句、领域和摘录语义校验。

    返回可审计的问题列表；空列表才表示质量门通过。这使报告不再仅因
    “数量恰好为 125”就误报 PASS。
    """

    issues: list[str] = []
    if len(items) != TARGET_COUNT:
        issues.append(f"抽取数量为 {len(items)}，目标为 {TARGET_COUNT}")

    expected_ids = [f"Q{i:03d}" for i in range(1, len(items) + 1)]
    actual_ids = [str(item.get("id", "")) for item in items]
    if actual_ids != expected_ids:
        issues.append("Q 编号不连续、重复或顺序异常")

    domain_counts = Counter(str(item.get("domain", "")) for item in items)
    for domain, expected_count in EXPECTED_DOMAIN_COUNTS.items():
        actual_count = domain_counts.get(domain, 0)
        if actual_count != expected_count:
            issues.append(f"领域数量异常: {domain}={actual_count}，预期 {expected_count}")

    seen_questions: set[str] = set()
    starter_pattern = re.compile(r"\b(?:" + "|".join(_QUESTION_STARTERS) + r")\b")
    for item in items:
        qid = str(item.get("id", "?"))
        question = re.sub(r"\s+", " ", str(item.get("question", ""))).strip()
        domain = str(item.get("domain", ""))
        if domain not in STANDARD_DOMAINS:
            issues.append(f"{qid}: 非标准领域 {domain!r}")
        if not question.endswith("?"):
            issues.append(f"{qid}: 问题未以问号结束")
        if not question.startswith(_QUESTION_STARTERS):
            issues.append(f"{qid}: 疑似残句（非疑问词开头）: {question}")
        # 两个大写疑问词却只有一个问号，是跨栏标题粘连的稳定特征。
        if len(starter_pattern.findall(question)) > question.count("?"):
            issues.append(f"{qid}: 疑似多个标题粘连: {question}")
        normalized = re.sub(r"[^a-z0-9]+", " ", question.lower()).strip()
        if normalized in seen_questions:
            issues.append(f"{qid}: 问题文本重复")
        seen_questions.add(normalized)

    by_question = {str(item.get("question", "")): item for item in items}
    semantic_contracts = {
        "riemann": ("riemann", "zeta"),
        "vaccines": ("vaccine", "covid-19"),
        "meridian": ("meridian", "acupuncture"),
        "ai_replace": ("uncertainty", "equivocality"),
        "hybrid": ("human–machine", "exoskeleton"),
        "quantum_brain": ("brain", "quantum"),
    }
    for key, required_terms in semantic_contracts.items():
        canonical = _CANONICAL_LAYOUT_ITEMS[key]
        title = canonical["question"]
        item = by_question.get(title)
        if item is None:
            issues.append(f"缺少关键问题: {title}")
            continue
        if item.get("domain") != canonical["domain"]:
            issues.append(f"{item.get('id', '?')}: 关键问题领域错配，应为 {canonical['domain']}")
        excerpt = str(item.get("booklet_excerpt", "")).lower()
        missing = [term for term in required_terms if term.lower() not in excerpt]
        if missing:
            issues.append(f"{item.get('id', '?')}: 摘录与题意不匹配，缺少语义锚点 {missing}")

    replace_item = by_question.get(_CANONICAL_LAYOUT_ITEMS["ai_replace"]["question"])
    if replace_item and "nanobot" in str(replace_item.get("booklet_excerpt", "")).lower():
        issues.append(f"{replace_item.get('id', '?')}: AI replace humans 摘录混入 nanobot 跨栏续文")

    return issues


def _confidence_for(q: dict) -> float:
    """
    依据启发式为问题分配置信度（供人工校验参考）。

    参数：
        q: 问题记录。

    返回：
        0-1 的置信度分数。
    """
    # 基础分：识别到标准领域且 excerpt 足够长者更可信。
    score = 0.9
    if q["domain"] == "Unknown":
        score -= 0.3
    if len(q["booklet_excerpt"]) < 120:
        score -= 0.15
    # 限制到 [0,1]。
    return round(max(0.0, min(1.0, score)), 2)


def ensure_pandemic(questions: list[dict]) -> bool:
    """
    确保关键 demo 问题被识别；若缺失但 PDF 中存在则 fallback 补入。

    参数：
        questions: 已抽取的问题列表（就地可能被追加）。

    返回：
        True 表示使用了 fallback 补入；False 表示原本即已识别。
    """
    # 已识别则无需 fallback。
    if any("predict the next pandemic" in q["question"].lower() for q in questions):
        return False

    # fallback：在 PDF 全文中搜索该问题原文，若存在则补入。
    try:
        import fitz
    except ImportError:
        return False
    doc = fitz.open(str(PDF_PATH))
    for pno in range(doc.page_count):
        page_text = normalize_text(doc[pno].get_text("text"))
        if "predict the next pandemic" in page_text.lower():
            questions.append(
                {
                    "question": PANDEMIC_QUESTION,
                    "domain": "Medicine & Health",
                    "source_page": pno + 1,
                    "booklet_excerpt": page_text[:800],
                    "_fallback": True,
                }
            )
            doc.close()
            return True
    doc.close()
    return False


def build_question_items(questions: list[dict], fallback_used: bool) -> list[dict]:
    """
    将问题记录编号为 Q001.. 并组装为 QuestionItem 兼容的 dict。

    参数：
        questions:     去重、排序后的问题列表。
        fallback_used: 是否对 pandemic 问题使用了 fallback。

    返回：
        QuestionItem 结构的 dict 列表（含 metadata）。
    """
    items: list[dict] = []
    for i, q in enumerate(questions, start=1):
        # 记录来源方式：固定版式校正项单独标记，便于审计。
        if q.get("_fallback"):
            method = "manual_seed"
        elif q.get("_layout_repaired"):
            method = "hybrid_layout_repair"
        else:
            method = "hybrid"
        items.append(
            {
                "id": f"Q{i:03d}",
                "domain": q["domain"],
                "question": q["question"],
                "source_page": q["source_page"],
                "booklet_excerpt": q["booklet_excerpt"],
                "metadata": {
                    "confidence": _confidence_for(q),
                    "extraction_method": method,
                    "source_file": "data/raw/sjtu-booklet.pdf",
                },
            }
        )
    return items


def write_outputs(
    items: list[dict],
    removed: list[dict],
    fallback_used: bool,
    layout_repairs: list[str] | None = None,
) -> str:
    """
    写出 JSON / CSV / extraction_report.md，并返回状态（PASS / WARNING）。

    参数：
        items:         最终 QuestionItem dict 列表。
        removed:       被去重的问题列表。
        fallback_used: 是否使用了 pandemic fallback。
        layout_repairs: 已应用的固定版式校正标识。

    返回：
        "PASS"（数量与语义质量门均通过）或 "WARNING"（任一检查失败）。
    """
    # 确保输出目录存在。
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # 写 JSON。
    JSON_PATH.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    # 写 CSV（列固定）。
    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["id", "domain", "question", "source_page", "booklet_excerpt", "confidence", "extraction_method"]
        )
        for it in items:
            writer.writerow(
                [
                    it["id"],
                    it["domain"],
                    it["question"],
                    it["source_page"],
                    it["booklet_excerpt"],
                    it["metadata"]["confidence"],
                    it["metadata"]["extraction_method"],
                ]
            )

    # 统计各领域数量与低置信问题。
    domain_counts = Counter(it["domain"] for it in items)
    low_conf = [it for it in items if it["metadata"]["confidence"] < 0.7]
    quality_issues = validate_question_items(items)
    status = "PASS" if not quality_issues else "WARNING"

    # 组装报告内容。
    lines: list[str] = []
    lines.append("# 125 问题抽取报告\n")
    lines.append(f"- 生成时间（UTC）：{datetime.now(timezone.utc).isoformat()}")
    lines.append(f"- 抽取数量：{len(items)}（目标 {TARGET_COUNT}）")
    lines.append(f"- 状态：**{status}**")
    lines.append(f"- 自动质量校验：{'PASS' if not quality_issues else f'FAIL（{len(quality_issues)} 项）'}")
    if fallback_used:
        lines.append("- manual_seed_fallback_used_for_pandemic_question")
    lines.append("")
    lines.append("## 各领域问题数量\n")
    for domain in STANDARD_DOMAINS:
        lines.append(f"- {domain}: {domain_counts.get(domain, 0)}")
    unknown = domain_counts.get("Unknown", 0)
    if unknown:
        lines.append(f"- Unknown（未归类，建议人工校验）: {unknown}")
    lines.append("")

    lines.append("## 语义与断句质量门\n")
    if quality_issues:
        for issue in quality_issues:
            lines.append(f"- FAIL: {issue}")
    else:
        lines.append("- PASS: 数量、Q 编号连续性、标题断句、标准领域与关键摘录语义均通过。")
    lines.append("")
    lines.append("## 固定版式校正审计\n")
    if layout_repairs:
        for repair in dict.fromkeys(layout_repairs):
            lines.append(f"- {repair}: 已按源 PDF 原文校正")
    else:
        lines.append("- （未触发校正）")
    lines.append("")

    if status == "PASS":
        # PASS：给出前 5 与后 5 预览。
        lines.append("## 前 5 个问题预览\n")
        for it in items[:5]:
            lines.append(f"- {it['id']} [{it['domain']}] {it['question']}")
        lines.append("")
        lines.append("## 后 5 个问题预览\n")
        for it in items[-5:]:
            lines.append(f"- {it['id']} [{it['domain']}] {it['question']}")
    else:
        # WARNING：详列疑点，避免静默成功。
        lines.append("## WARNING 详情（请人工校验）\n")
        if len(items) != TARGET_COUNT:
            lines.append(f"- 抽取数量为 {len(items)}，与目标 {TARGET_COUNT} 不符。")
        else:
            lines.append("- 抽取数量为 125，但语义/断句/领域质量门未全部通过。")
        lines.append(f"- 低置信问题数：{len(low_conf)}")
        for it in low_conf:
            lines.append(f"  - {it['id']} [{it['domain']}] (conf={it['metadata']['confidence']}) {it['question']}")
        lines.append(f"- 被去重问题数：{len(removed)}")
        for q in removed:
            lines.append(f"  - [p{q.get('source_page')}] {q.get('question')}")
        lines.append("- 建议：核对上述页面是否存在漏抽/误抽，并人工校验领域归类。")

    lines.append("")
    lines.append("## 被去重的问题\n")
    if removed:
        for q in removed:
            lines.append(f"- [p{q.get('source_page')}] {q.get('question')}")
    else:
        lines.append("- （无）")

    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return status


def main() -> int:
    """
    脚本主入口：检查 PDF -> 抽取 -> 去重 -> fallback -> 编号 -> 写出报告。

    返回：
        进程退出码（PDF 缺失返回非 0；其余返回 0，即使 WARNING 也保存结果）。
    """
    # PDF 存在性检查：缺失则清晰报错并非 0 退出。
    if not PDF_PATH.exists():
        logger.error("未找到 PDF，请将 sjtu-booklet.pdf 放到 data/raw/sjtu-booklet.pdf")
        print("错误：请将 sjtu-booklet.pdf 放到 data/raw/sjtu-booklet.pdf")
        return 2

    logger.info("开始抽取 125 问题：%s", PDF_PATH)
    # 抽取原始问题。
    raw = extract_raw_questions()
    # 校正固定双栏版式导致的标题、领域与摘录错配。
    layout_repairs = repair_known_layout_anomalies(raw)
    # 去重。
    unique, removed = deduplicate_questions(raw)
    # 确保 pandemic 问题存在（必要时 fallback）。
    fallback_used = ensure_pandemic(unique)
    # 编号并组装。
    items = build_question_items(unique, fallback_used)
    # 写出结果与报告。
    status = write_outputs(items, removed, fallback_used, layout_repairs)

    # 控制台摘要（不含任何敏感信息）。
    logger.info("抽取完成：数量=%d，状态=%s", len(items), status)
    print(f"抽取完成：共 {len(items)} 个问题，状态 {status}")
    print(f"JSON: {JSON_PATH}")
    print(f"CSV : {CSV_PATH}")
    print(f"报告: {REPORT_PATH}")
    if status != "PASS":
        print("注意：数量或语义质量门未通过，请查看 extraction_report.md 中的 WARNING 详情。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
