"""Deterministic scientific-output fingerprints and similarity scoring."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable


DEFAULT_TEMPLATE_PHRASES = (
    "this study proposes",
    "we present",
    "the results show",
    "further research is needed",
)


@dataclass(frozen=True, slots=True)
class OutputFingerprint:
    title_sha256: str
    abstract_sha256: str
    hypothesis_sha256: str
    combined_sha256: str
    normalized_title: str
    normalized_abstract: str
    normalized_hypothesis: str


@dataclass(frozen=True, slots=True)
class FieldSimilarity:
    field: str
    token_overlap: float
    sequence: float
    score: float
    exact_hash_match: bool
    template_only: bool


@dataclass(frozen=True, slots=True)
class CrossQuestionSimilarity:
    left_question_id: str
    right_question_id: str
    compared: bool
    reason: str
    title: FieldSimilarity
    abstract: FieldSimilarity
    hypothesis: FieldSimilarity
    combined_score: float
    threshold: float
    requires_review: bool


def normalize_scientific_text(value: str) -> str:
    """Apply NFKC, casefold, punctuation boundaries, and whitespace folding."""

    if not isinstance(value, str):
        raise TypeError("scientific text must be a string")
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = "".join(
        " " if unicodedata.category(character).startswith("P") else character
        for character in normalized
    )
    return re.sub(r"\s+", " ", normalized).strip()


def build_text_sha256(value: str) -> str:
    """Hash normalized UTF-8 content without question identity."""

    normalized = normalize_scientific_text(value)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def build_output_fingerprint(
    *,
    title: str,
    abstract: str,
    hypothesis: str,
) -> OutputFingerprint:
    """Build independent field hashes and a deterministic combined hash."""

    normalized = {
        "abstract": normalize_scientific_text(abstract),
        "hypothesis": normalize_scientific_text(hypothesis),
        "title": normalize_scientific_text(title),
    }
    combined = json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return OutputFingerprint(
        title_sha256=hashlib.sha256(
            normalized["title"].encode("utf-8")
        ).hexdigest(),
        abstract_sha256=hashlib.sha256(
            normalized["abstract"].encode("utf-8")
        ).hexdigest(),
        hypothesis_sha256=hashlib.sha256(
            normalized["hypothesis"].encode("utf-8")
        ).hexdigest(),
        combined_sha256=hashlib.sha256(combined).hexdigest(),
        normalized_title=normalized["title"],
        normalized_abstract=normalized["abstract"],
        normalized_hypothesis=normalized["hypothesis"],
    )


def token_overlap_similarity(left: str, right: str) -> float:
    """Return normalized-token Jaccard similarity in the 0..1 range."""

    left_tokens = set(normalize_scientific_text(left).split())
    right_tokens = set(normalize_scientific_text(right).split())
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def sequence_similarity(left: str, right: str) -> float:
    """Return deterministic normalized-text sequence similarity."""

    normalized_left = normalize_scientific_text(left)
    normalized_right = normalize_scientific_text(right)
    if not normalized_left or not normalized_right:
        return 0.0
    return SequenceMatcher(
        None,
        normalized_left,
        normalized_right,
        autojunk=False,
    ).ratio()


def evaluate_cross_question_similarity(
    *,
    left_question_id: str,
    left: OutputFingerprint,
    right_question_id: str,
    right: OutputFingerprint,
    threshold: float = 0.90,
    template_phrases: Iterable[str] = DEFAULT_TEMPLATE_PHRASES,
) -> CrossQuestionSimilarity:
    """Compare distinct questions with auditable field-level components."""

    left_id = _require_question_id(left_question_id, "left_question_id")
    right_id = _require_question_id(right_question_id, "right_question_id")
    if not isinstance(threshold, (int, float)) or isinstance(threshold, bool):
        raise TypeError("threshold must be numeric")
    normalized_threshold = float(threshold)
    if not 0.0 <= normalized_threshold <= 1.0:
        raise ValueError("threshold must be between 0 and 1")

    phrases = tuple(
        normalize_scientific_text(value) for value in template_phrases
    )
    title = _field_similarity(
        "title",
        left.normalized_title,
        right.normalized_title,
        left.title_sha256,
        right.title_sha256,
        phrases,
    )
    abstract = _field_similarity(
        "abstract",
        left.normalized_abstract,
        right.normalized_abstract,
        left.abstract_sha256,
        right.abstract_sha256,
        phrases,
    )
    hypothesis = _field_similarity(
        "hypothesis",
        left.normalized_hypothesis,
        right.normalized_hypothesis,
        left.hypothesis_sha256,
        right.hypothesis_sha256,
        phrases,
    )

    if left_id == right_id:
        return CrossQuestionSimilarity(
            left_question_id=left_id,
            right_question_id=right_id,
            compared=False,
            reason="same-question retry is outside cross-question comparison",
            title=title,
            abstract=abstract,
            hypothesis=hypothesis,
            combined_score=0.0,
            threshold=normalized_threshold,
            requires_review=False,
        )

    weighted_fields = (
        (title, 0.25, left.normalized_title, right.normalized_title),
        (abstract, 0.50, left.normalized_abstract, right.normalized_abstract),
        (
            hypothesis,
            0.25,
            left.normalized_hypothesis,
            right.normalized_hypothesis,
        ),
    )
    active = [
        (result, weight)
        for result, weight, left_value, right_value in weighted_fields
        if left_value and right_value and not result.template_only
    ]
    weight_total = sum(weight for _, weight in active)
    combined = (
        sum(result.score * weight for result, weight in active) / weight_total
        if weight_total
        else 0.0
    )
    combined = round(combined, 6)
    return CrossQuestionSimilarity(
        left_question_id=left_id,
        right_question_id=right_id,
        compared=True,
        reason="distinct question_id values compared",
        title=title,
        abstract=abstract,
        hypothesis=hypothesis,
        combined_score=combined,
        threshold=normalized_threshold,
        requires_review=combined > normalized_threshold,
    )


def _field_similarity(
    field_name: str,
    left: str,
    right: str,
    left_hash: str,
    right_hash: str,
    template_phrases: tuple[str, ...],
) -> FieldSimilarity:
    stripped_left = _remove_template_phrases(left, template_phrases)
    stripped_right = _remove_template_phrases(right, template_phrases)
    template_only = (
        bool(left and right) and not stripped_left and not stripped_right
    )
    token_score = token_overlap_similarity(stripped_left, stripped_right)
    sequence_score = sequence_similarity(stripped_left, stripped_right)
    exact = bool(left and right) and left_hash == right_hash
    if template_only:
        score = 0.0
    elif exact:
        score = 1.0
    else:
        score = 0.4 * token_score + 0.6 * sequence_score
    return FieldSimilarity(
        field=field_name,
        token_overlap=round(token_score, 6),
        sequence=round(sequence_score, 6),
        score=round(score, 6),
        exact_hash_match=exact,
        template_only=template_only,
    )


def _remove_template_phrases(
    value: str,
    template_phrases: tuple[str, ...],
) -> str:
    result = value
    for phrase in template_phrases:
        if phrase:
            result = re.sub(
                rf"(?<!\w){re.escape(phrase)}(?!\w)",
                " ",
                result,
            )
    return re.sub(r"\s+", " ", result).strip()


def _require_question_id(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"{field_name} must be a non-empty string")
    return value.strip()
