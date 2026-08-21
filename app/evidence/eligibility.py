"""Eligibility grades for scholarly evidence. Metadata cannot support facts."""

from __future__ import annotations

from enum import StrEnum


class SourceEligibility(StrEnum):
    FULLTEXT_VERIFIED = "FULLTEXT_VERIFIED"
    ABSTRACT_VERIFIED = "ABSTRACT_VERIFIED"
    METADATA_ONLY = "METADATA_ONLY"
    QUESTION_SOURCE = "QUESTION_SOURCE"
    FETCH_FAILED = "FETCH_FAILED"
    LICENSE_RESTRICTED = "LICENSE_RESTRICTED"


FACT_ELIGIBLE = frozenset(
    {
        SourceEligibility.FULLTEXT_VERIFIED,
        SourceEligibility.ABSTRACT_VERIFIED,
    }
)

FORBIDDEN_EVIDENCE_ID_PATTERNS = (
    r"^Q\d{3}_booklet$",
    r"^booklet_excerpt_Q\d{3}$",
    r"^Q\d{3}_question_source$",
    r"^title_only_",
    r"^doi_only_",
)

ELIGIBILITY_NOTE_PREFIX = "eligibility_status="
