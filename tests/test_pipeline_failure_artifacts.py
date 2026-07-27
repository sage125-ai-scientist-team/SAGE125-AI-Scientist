"""An early real/mock failure must remain diagnosable and visible to progress UI."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app.agents.base import AgentOutputError
from app.workflow.pipeline import run_pipeline_with_state
from tests.helpers_questions_fixture import write_minimal_questions_fixture


def test_first_agent_failure_persists_partial_state(monkeypatch, tmp_path):
    """First-agent failure keeps partial artifacts even without repo questions_125.json."""
    fixture = write_minimal_questions_fixture(tmp_path / "questions_125.json", question_id="Q001")
    monkeypatch.setenv("SAGE_QUESTIONS_PATH", str(fixture))

    def _fail(*_args, **_kwargs):
        raise AgentOutputError("synthetic connection failure")

    monkeypatch.setattr("app.workflow.pipeline.QuestionParserAgent.run", _fail)
    events = []
    with pytest.raises(AgentOutputError) as exc_info:
        run_pipeline_with_state("Q001", mock_mode=True, progress_callback=events.append)

    run_id = getattr(exc_info.value, "run_id", "")
    assert run_id
    run_dir = Path(os.environ["SAGE_TEST_EXPORT_DIR"]) / run_id
    for name in (
        "run_status.json", "errors.json", "warnings.json", "agent_trace.json",
        "pipeline_state.json", "llm_call_audit.json",
    ):
        assert (run_dir / name).exists(), name
    status = json.loads((run_dir / "run_status.json").read_text(encoding="utf-8"))
    assert status["status"] == "failed"
    assert any(event.get("status") == "failed" for event in events)
