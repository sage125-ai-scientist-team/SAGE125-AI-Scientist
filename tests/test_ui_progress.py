"""运行进度组件：阶段稳定性、脱敏和三态渲染。"""

from __future__ import annotations

from pathlib import Path

from app.ui import components
from app.ui.job_state import run_progress_payload
from app.ui.progress import PIPELINE_STAGES, PIPELINE_STAGE_ORDER, normalize_progress


def test_pipeline_stage_order_is_stable_and_monotonic():
    assert PIPELINE_STAGE_ORDER[0] == "preparing"
    assert PIPELINE_STAGE_ORDER[-1] == "completed"
    assert len(PIPELINE_STAGE_ORDER) == len(set(PIPELINE_STAGE_ORDER))
    assert [stage.percent for stage in PIPELINE_STAGES] == sorted(stage.percent for stage in PIPELINE_STAGES)


def test_normalize_progress_clamps_percent_and_maps_friendly_model():
    snapshot = normalize_progress({
        "stage": "hypothesis_generator",
        "status": "waiting",
        "percent": 131,
        "model_alias": "strong",
        "model_name_internal": "qwen3.7-max",
    })

    assert snapshot.percent == 100
    assert snapshot.stage_label == "生成可证伪假设"
    assert snapshot.model_display == "千问 3.7 Max"
    assert snapshot.message == "正在等待千问 3.7 Max响应。"


def test_completed_always_uses_one_hundred_percent():
    snapshot = normalize_progress({"stage": "report_writer", "status": "success", "percent": 84})
    assert snapshot.status == "completed"
    assert snapshot.percent == 100


def test_public_message_redacts_internal_details_and_unsafe_text():
    snapshot = normalize_progress({
        "stage": "question_parser",
        "status": "running",
        "model_alias": "fast",
        "model_name_internal": "qwen3.6-flash",
        "message": "qwen3.6-flash 请求 https://example.invalid/v1，凭证 sk-secretsecret123",
    })

    assert "qwen3.6-flash" not in snapshot.message
    assert "https://" not in snapshot.message
    assert "sk-secret" not in snapshot.message
    assert "千问 3.6 Flash" in snapshot.message


def test_unknown_stage_and_bad_percent_have_safe_fallbacks():
    snapshot = normalize_progress({"stage": "<script>", "status": "mystery", "percent": "bad"})
    assert snapshot.stage == "preparing"
    assert snapshot.status == "running"
    assert snapshot.percent == 2


def test_component_hides_internal_model_by_default(monkeypatch):
    rendered: list[str] = []

    def fake_markdown(body, **_kwargs):
        rendered.append(body)

    monkeypatch.setattr(components.st, "markdown", fake_markdown)
    components.render_run_progress({
        "stage": "scientific_reviewer",
        "status": "connecting",
        "percent": 76,
        "model_alias": "strong",
        "model_display": "千问 3.7 Max",
        "model_name_internal": "qwen3.7-max-internal",
    })

    html = rendered[-1]
    assert "千问 3.7 Max" in html
    assert "qwen3.7-max-internal" not in html
    assert 'role="progressbar"' in html
    assert 'aria-valuenow="76"' in html


def test_component_can_show_internal_name_only_in_diagnostics(monkeypatch):
    rendered: list[str] = []
    monkeypatch.setattr(components.st, "markdown", lambda body, **_kwargs: rendered.append(body))

    components.render_run_progress({
        "stage": "report_writer",
        "status": "failed",
        "percent": 87,
        "model_alias": "balanced",
        "model_name_internal": "private-model-id",
    }, diagnostics=True)

    html = rendered[-1]
    assert "state-failed" in html
    assert "开发者诊断（默认折叠）" in html
    assert "private-model-id" in html


def test_run_progress_payload_maps_job_to_model_card():
    payload = run_progress_payload({
        "status": "running",
        "stage": "question_parser",
        "progress_percent": 16,
        "message": "正在连接 千问 3.6 Flash",
        "model_alias": "fast",
    })
    snapshot = normalize_progress(payload)
    assert payload["percent"] == 16
    assert payload["model_alias"] == "fast"
    assert snapshot.stage_label == "解析科学问题"
    assert "千问 3.6 Flash" in snapshot.message


def test_questions_page_uses_model_progress_not_pipeline_kpi():
    source = Path("app/ui/workspace_pages.py").read_text(encoding="utf-8")
    assert "_render_model_progress" in source
    assert 'ws-kpi-label">当前流程进度' not in source
    assert "流水线执行中" not in source
