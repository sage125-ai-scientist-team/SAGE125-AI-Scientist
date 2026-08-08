"""
T01 Wave C — 内容哈希缓存与确定性工具。

同输入必须产生稳定证据集合顺序与稳定指纹；缓存按原文键控，
命中时不得再次调用 ``hash_fn``，且不得因 dict 遍历顺序导致非确定性。
"""

from __future__ import annotations

import hashlib
import threading
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional, Sequence

from app.contracts.evidence import EvidenceBundle, EvidenceCardContract
from app.evidence.bundle_builder import compute_content_hash
from app.evidence.integration_bridge import bundle_fingerprint


@dataclass
class CacheStats:
    """
    缓存命中统计。

    属性：
        hits: 命中次数（未调用 hash_fn）。
        misses: 未命中次数（调用了 hash_fn）。
        size: 当前条目数。
        hash_fn_calls: hash_fn 实际调用次数。
    """

    hits: int = 0
    misses: int = 0
    size: int = 0
    hash_fn_calls: int = 0


@dataclass
class ContentHashCache:
    """
    线程安全的原文 → content_hash 缓存（附 hash→原文反查）。

    属性：
        _text_to_hash: quoted_text → digest（命中时跳过 hash_fn）。
        _store: digest → quoted_text。
        _lock: 线程锁。
        stats: 命中统计。
    """

    _text_to_hash: dict[str, str] = field(default_factory=dict)
    _store: dict[str, str] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    stats: CacheStats = field(default_factory=CacheStats)

    def get(self, content_hash: str) -> Optional[str]:
        """
        按哈希读取缓存摘录。

        参数：
            content_hash: 内容哈希键。

        返回：
            命中时返回摘录，否则 None。
        """
        with self._lock:
            value = self._store.get(content_hash)
            if value is None:
                self.stats.misses += 1
            else:
                self.stats.hits += 1
            self.stats.size = len(self._store)
            return value

    def put(self, content_hash: str, quoted_text: str) -> None:
        """
        写入缓存条目（双向索引）。

        参数：
            content_hash: 哈希键。
            quoted_text: 规范化摘录文本。
        """
        with self._lock:
            self._store[content_hash] = quoted_text
            self._text_to_hash[quoted_text] = content_hash
            self.stats.size = len(self._store)

    def get_or_compute(
        self,
        quoted_text: str,
        *,
        hash_fn: Callable[[str], str] = compute_content_hash,
    ) -> str:
        """
        计算或复用 content_hash；命中时不调用 ``hash_fn``。

        参数：
            quoted_text: 原文摘录。
            hash_fn: 哈希函数，默认 ``compute_content_hash``。

        返回：
            content_hash 字符串。
        """
        with self._lock:
            cached_digest = self._text_to_hash.get(quoted_text)
            if cached_digest is not None:
                self.stats.hits += 1
                self.stats.size = len(self._store)
                return cached_digest
            self.stats.misses += 1
            digest = hash_fn(quoted_text)
            self.stats.hash_fn_calls += 1
            self._text_to_hash[quoted_text] = digest
            self._store[digest] = quoted_text
            self.stats.size = len(self._store)
            return digest

    def clear(self) -> None:
        """
        清空缓存并重置统计。
        """
        with self._lock:
            self._store.clear()
            self._text_to_hash.clear()
            self.stats = CacheStats()


_GLOBAL_CACHE = ContentHashCache()


def get_global_content_hash_cache() -> ContentHashCache:
    """
    返回进程级全局内容哈希缓存实例。

    返回：
        ContentHashCache 单例。
    """
    return _GLOBAL_CACHE


def stable_sort_evidence_ids(evidence_ids: Iterable[str]) -> list[str]:
    """
    对证据 ID 做确定性排序（字典序）。

    参数：
        evidence_ids: 任意可迭代 ID。

    返回：
        排序后的列表。
    """
    return sorted({str(item) for item in evidence_ids})


def stable_evidence_set_fingerprint(
    evidences: Sequence[EvidenceCardContract],
) -> str:
    """
    仅基于证据 ID + content_hash 的稳定集合指纹。

    参数：
        evidences: 证据卡序列。

    返回：
        sha256 hex。
    """
    rows = []
    for card in evidences:
        digest = card.content_hash or compute_content_hash(card.quoted_text)
        rows.append(f"{card.evidence_id}|{digest}")
    payload = "\n".join(sorted(rows)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def deterministic_bundle_digest(bundle: EvidenceBundle) -> str:
    """
    计算 Bundle 确定性摘要（复用 integration_bridge 指纹）。

    参数：
        bundle: EvidenceBundle。

    返回：
        64 位 hex。
    """
    return bundle_fingerprint(bundle)


def assert_same_input_stable_evidence_set(
    left: EvidenceBundle,
    right: EvidenceBundle,
) -> None:
    """
    断言两份同输入 Bundle 的证据集合指纹一致。

    参数：
        left / right: 待比较 Bundle。

    异常：
        AssertionError: 指纹不一致。
    """
    left_fp = stable_evidence_set_fingerprint(left.evidences)
    right_fp = stable_evidence_set_fingerprint(right.evidences)
    if left_fp != right_fp:
        raise AssertionError(
            f"evidence set unstable: {left_fp} != {right_fp}"
        )
    if deterministic_bundle_digest(left) != deterministic_bundle_digest(right):
        raise AssertionError("bundle digest unstable across same input")
