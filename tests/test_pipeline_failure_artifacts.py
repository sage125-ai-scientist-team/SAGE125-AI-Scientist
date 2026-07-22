"""An early real/mock failure must remain diagnosable and visible to progress UI."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app.agents.base import AgentOutputError
from app.workflow.pipeline import run_pipeline_with_state


def test_first_agent_failure_persists_partial_state(monkeypatch):
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

