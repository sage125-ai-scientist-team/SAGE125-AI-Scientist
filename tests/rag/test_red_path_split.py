"""Red test: Supervisor behavior still checks the legacy index path."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.agents.supervisor import SupervisorAgent


@pytest.mark.xfail(
    reason="Supervisor path routing waiting for owner/shared-change",
    strict=True,
)
def test_supervisor_enables_rag_when_only_formal_user_library_index_exists(tmp_path):
    """Expected red: a ready formal index must enable Local RAG."""

    data_root = tmp_path / "data"
    formal_index = data_root / "index" / "user_library" / "zvec"
    formal_index.mkdir(parents=True)
    (formal_index / "READY").write_text("offline fixture", encoding="utf-8")
    assert not (data_root / "index" / "zvec").exists()

    settings = SimpleNamespace(
        data_dir=str(data_root),
        qwen_balanced_model="qwen3.7-plus",
        deep_research_configured=False,
        openalex_configured=False,
    )
    state = SimpleNamespace(run_id="RED-PATH", agent_trace=[])
    result = SupervisorAgent(settings=settings).run(
        {
            "switches": {
                "use_local_rag": True,
                "use_deep_research": False,
                "use_open_literature": False,
                "mock_mode": False,
            }
        },
        state,
    )

    assert result["execution_plan"]["use_local_rag"] is True
