"""Stable, transport-neutral errors for the T03 feedback boundary."""

from __future__ import annotations

from enum import Enum


class FeedbackErrorCode(str, Enum):
    """Machine-readable error codes consumed by T02 and T08 adapters."""

    INVALID_INPUT = "feedback.invalid_input"
    UNSAFE_INPUT = "feedback.unsafe_input"
    PERMISSION_DENIED = "feedback.permission_denied"
    NOT_FOUND = "feedback.not_found"
    LINEAGE_NOT_FOUND = "feedback.lineage_not_found"
    CONFLICT = "feedback.conflict"
    IDEMPOTENCY_CONFLICT = "feedback.idempotency_conflict"
    FINGERPRINT_CONFLICT = "feedback.fingerprint_conflict"
    STORAGE_FAILURE = "feedback.storage_failure"
    CORRUPT_SNAPSHOT = "feedback.corrupt_snapshot"
    UNSUPPORTED_SCHEMA = "feedback.unsupported_schema"


class FeedbackError(Exception):
    """Base exception whose ``code`` is safe to expose at an API boundary."""

    default_code = FeedbackErrorCode.INVALID_INPUT

    def __init__(
        self,
        message: str,
        *,
        code: FeedbackErrorCode | str | None = None,
    ) -> None:
        super().__init__(message)
        selected = code or self.default_code
        self.code = selected.value if isinstance(selected, FeedbackErrorCode) else selected


class InvalidFeedbackInput(FeedbackError, ValueError):
    default_code = FeedbackErrorCode.INVALID_INPUT


class UnsafeFeedbackInput(InvalidFeedbackInput):
    default_code = FeedbackErrorCode.UNSAFE_INPUT


class FeedbackPermissionDenied(FeedbackError, PermissionError):
    default_code = FeedbackErrorCode.PERMISSION_DENIED


class FeedbackNotFound(FeedbackError, KeyError):
    default_code = FeedbackErrorCode.NOT_FOUND


class LineageNotFound(FeedbackNotFound):
    default_code = FeedbackErrorCode.LINEAGE_NOT_FOUND


class FeedbackConflict(FeedbackError):
    default_code = FeedbackErrorCode.CONFLICT


class IdempotencyConflict(FeedbackConflict):
    default_code = FeedbackErrorCode.IDEMPOTENCY_CONFLICT


class FingerprintConflict(FeedbackConflict):
    default_code = FeedbackErrorCode.FINGERPRINT_CONFLICT


class FeedbackStorageError(FeedbackError):
    default_code = FeedbackErrorCode.STORAGE_FAILURE


class CorruptFeedbackSnapshot(FeedbackStorageError):
    default_code = FeedbackErrorCode.CORRUPT_SNAPSHOT


class UnsupportedFeedbackSchema(FeedbackStorageError):
    default_code = FeedbackErrorCode.UNSUPPORTED_SCHEMA


# Descriptive aliases keep integration code readable without changing codes.
FeedbackNotFoundError = FeedbackNotFound
FeedbackConflictError = FeedbackConflict
FeedbackAuthorizationError = FeedbackPermissionDenied
FeedbackValidationError = InvalidFeedbackInput


__all__ = [
    "CorruptFeedbackSnapshot",
    "FeedbackAuthorizationError",
    "FeedbackConflict",
    "FeedbackConflictError",
    "FeedbackError",
    "FeedbackErrorCode",
    "FeedbackNotFound",
    "FeedbackNotFoundError",
    "FeedbackPermissionDenied",
    "FeedbackStorageError",
    "FeedbackValidationError",
    "FingerprintConflict",
    "IdempotencyConflict",
    "InvalidFeedbackInput",
    "LineageNotFound",
    "UnsafeFeedbackInput",
    "UnsupportedFeedbackSchema",
]
