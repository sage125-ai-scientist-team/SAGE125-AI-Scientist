"""The Wave A ports stay implementable without importing pipeline or API code."""

from __future__ import annotations

from app.feedback.service import FeedbackService
from app.feedback.storage import FeedbackStore
from app.quality.service import QualityGate, QualityGateRunner
from app.validation.service import ValidationService


def test_ports_are_runtime_checkable_protocols() -> None:
    for port in (
        FeedbackStore,
        FeedbackService,
        QualityGate,
        QualityGateRunner,
        ValidationService,
    ):
        assert getattr(port, "_is_runtime_protocol", False)
