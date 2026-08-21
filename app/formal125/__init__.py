"""Formal 125-question preflight: catalog, locks, authorization, offline dry-run."""

from __future__ import annotations

FORMAL_125_PREFLIGHT_ID = "CAPTAIN-LOCAL-FORMAL-125-PREFLIGHT-01"
FORMAL_125_LOCK_VERSION = "formal125.lock.v1"
EXPECTED_QUESTION_COUNT = 125
BOOKLET_DOMAIN_COUNT = 12
SIMILARITY_REVIEW_THRESHOLD = 0.90
REQUIRED_RESULT_FILES = (
    "result.md",
    "result.json",
    "result.pdf",
    "evidence_cards.json",
    "agent_trace.json",
    "validation.json",
    "provider_audit.json",
    "package_manifest.json",
    "checksums.sha256",
)

__all__ = [
    "EXPECTED_QUESTION_COUNT",
    "FORMAL_125_LOCK_VERSION",
    "FORMAL_125_PREFLIGHT_ID",
    "REQUIRED_RESULT_FILES",
    "SIMILARITY_REVIEW_THRESHOLD",
]
