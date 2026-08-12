"""Wave B deterministic scientific-text fingerprint tests."""

from __future__ import annotations

import pytest


def _api():
    import app.batch.fingerprint as fingerprint

    return fingerprint


def _fingerprint(**changes: str):
    values = {
        "title": "Synthetic pandemic response optimization",
        "abstract": "Mobility controls and vaccination schedules are evaluated.",
        "hypothesis": "Joint controls reduce synthetic peak demand.",
    }
    values.update(changes)
    return _api().build_output_fingerprint(**values)


def test_identical_text_has_identical_hash() -> None:
    api = _api()
    assert api.build_text_sha256("Synthetic result") == api.build_text_sha256(
        "Synthetic result"
    )


def test_case_whitespace_and_newlines_are_normalized() -> None:
    api = _api()
    left = "  SYNTHETIC\n\nResult   With\tSpacing "
    right = "synthetic result with spacing"

    assert api.normalize_scientific_text(left) == right
    assert api.build_text_sha256(left) == api.build_text_sha256(right)


def test_common_punctuation_differences_are_normalized() -> None:
    api = _api()
    left = "Alpha—beta，gamma；delta。"
    right = "alpha beta gamma delta"

    assert api.normalize_scientific_text(left) == right
    assert api.build_text_sha256(left) == api.build_text_sha256(right)


def test_different_text_has_different_hash() -> None:
    api = _api()
    assert api.build_text_sha256("synthetic alpha") != api.build_text_sha256(
        "synthetic beta"
    )


def test_output_fields_have_independent_hashes() -> None:
    api = _api()
    fingerprint = _fingerprint()

    assert fingerprint.title_sha256 == api.build_text_sha256(
        "Synthetic pandemic response optimization"
    )
    assert fingerprint.abstract_sha256 == api.build_text_sha256(
        "Mobility controls and vaccination schedules are evaluated."
    )
    assert fingerprint.hypothesis_sha256 == api.build_text_sha256(
        "Joint controls reduce synthetic peak demand."
    )
    assert len(
        {
            fingerprint.title_sha256,
            fingerprint.abstract_sha256,
            fingerprint.hypothesis_sha256,
        }
    ) == 3


def test_combined_fingerprint_is_deterministic() -> None:
    assert _fingerprint().combined_sha256 == _fingerprint().combined_sha256


def test_combined_fingerprint_changes_when_one_field_changes() -> None:
    original = _fingerprint()
    changed = _fingerprint(hypothesis="A distinct synthetic hypothesis")

    assert changed.title_sha256 == original.title_sha256
    assert changed.abstract_sha256 == original.abstract_sha256
    assert changed.hypothesis_sha256 != original.hypothesis_sha256
    assert changed.combined_sha256 != original.combined_sha256


def test_question_id_is_not_part_of_content_hash_api() -> None:
    first = _fingerprint()
    second = _fingerprint()

    assert first == second
    assert "question_id" not in first.__dataclass_fields__


def test_empty_fields_are_safe_and_deterministic() -> None:
    api = _api()
    first = api.build_output_fingerprint(title="", abstract="", hypothesis="")
    second = api.build_output_fingerprint(title="", abstract="", hypothesis="")

    assert first == second
    assert first.normalized_title == ""
    assert first.normalized_abstract == ""
    assert first.normalized_hypothesis == ""


@pytest.mark.parametrize("value", [None, 1, object(), ["text"]])
def test_non_string_input_fails_closed(value: object) -> None:
    with pytest.raises(TypeError, match="must be a string"):
        _api().normalize_scientific_text(value)  # type: ignore[arg-type]


def test_token_and_sequence_similarity_are_bounded() -> None:
    api = _api()
    token_score = api.token_overlap_similarity("alpha beta", "alpha gamma")
    sequence_score = api.sequence_similarity("alpha beta", "alpha gamma")

    assert 0.0 <= token_score <= 1.0
    assert 0.0 <= sequence_score <= 1.0


def test_similarity_preserves_each_field_score_and_combined_result() -> None:
    left = _fingerprint()
    right = _fingerprint(hypothesis="A distinct synthetic hypothesis")

    result = _api().evaluate_cross_question_similarity(
        left_question_id="Q901",
        left=left,
        right_question_id="Q902",
        right=right,
    )

    assert result.compared is True
    assert result.title.score == 1.0
    assert result.abstract.score == 1.0
    assert 0.0 <= result.hypothesis.score < 1.0
    assert 0.0 <= result.combined_score <= 1.0


def test_same_question_retry_is_not_cross_question_similarity() -> None:
    fingerprint = _fingerprint()

    result = _api().evaluate_cross_question_similarity(
        left_question_id="Q901",
        left=fingerprint,
        right_question_id="Q901",
        right=fingerprint,
    )

    assert result.compared is False
    assert result.requires_review is False
    assert result.combined_score == 0.0
