"""Question selector uses stable QIDs and atomically syncs pending choices."""

from __future__ import annotations

import streamlit as st

from app.ui import components, state


class _Column:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def test_selector_uses_qid_and_card_matches_selected_question(monkeypatch):
    questions = [
        {"id": "Q001", "question": "Prime numbers?", "domain": "Math", "source_page": 1, "booklet_excerpt": "prime"},
        {"id": "Q024", "question": "Can xenotransplantation help?", "domain": "Medicine", "source_page": 2, "booklet_excerpt": "xeno"},
    ]
    rendered: list[str] = []
    seen: dict = {}
    original_session = st.session_state
    st.session_state = {}  # type: ignore[assignment]

    def fake_selectbox(label, options, **kwargs):
        if label == "领域过滤":
            return "全部"
        seen["options"] = list(options)
        seen["index"] = kwargs.get("index")
        return list(options)[kwargs.get("index", 0)]

    try:
        monkeypatch.setattr(components.st, "columns", lambda _spec: [_Column(), _Column()])
        monkeypatch.setattr(components.st, "text_input", lambda *_a, **_k: "")
        monkeypatch.setattr(components.st, "selectbox", fake_selectbox)
        monkeypatch.setattr(components.st, "markdown", lambda text, **_k: rendered.append(text))
        qid = components.render_question_selector(questions, selected_qid="Q024")
    finally:
        st.session_state = original_session  # type: ignore[assignment]

    assert seen["options"] == ["Q001", "Q024"]
    assert seen["index"] == 1
    assert qid == "Q024"
    assert any("Q024" in html and "Can xenotransplantation help?" in html for html in rendered)


def test_pending_question_selection_is_consumed_once():
    original_session = st.session_state
    st.session_state = {}  # type: ignore[assignment]
    try:
        state.init_state()
        state.queue_question_selection("Q024")
        assert state.consume_question_selection() == "Q024"
        assert state.consume_question_selection() is None
    finally:
        st.session_state = original_session  # type: ignore[assignment]

