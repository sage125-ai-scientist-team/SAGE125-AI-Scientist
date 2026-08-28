"""
tests/test_api_smoke.py — API 接口 smoke（TestClient，无真实 LLM 调用）。

覆盖：/health 不含 Key；/questions 可返回；/diagnostics 可返回；
/runs 列表可返回；无 submission/technical_solution/demo_script 路由。
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from typing import Any

import pytest
from fastapi.testclient import TestClient

try:
    from fastapi.routing import iter_route_contexts as _iter_route_contexts
except ImportError:
    _iter_route_contexts = None

from app.api.main import app

client = TestClient(app)


def _runtime_route_paths(routes: Sequence[Any]) -> list[str]:
    """Enumerate runtime routes across flat and public route-tree models."""
    if _iter_route_contexts is not None:
        paths = [context.path for context in _iter_route_contexts(routes)]
    else:
        try:
            paths = [route.path for route in routes]
        except AttributeError as exc:
            raise AssertionError(
                "UNSUPPORTED_ROUTE_TREE_WITHOUT_PUBLIC_ITERATOR: "
                "runtime route node has no .path"
            ) from exc

    assert paths, "runtime route enumeration unexpectedly returned no paths"
    assert all(isinstance(path, str) and path for path in paths)
    return paths


def test_health_no_key():
    """/health 返回 200 且不含明文 Key。"""
    r = client.get("/health")
    assert r.status_code == 200
    assert "sk-" not in json.dumps(r.json())
    # 含模型名。
    assert r.json()["models"]["embedding"] == "text-embedding-v4"


def test_questions():
    """/questions 返回 200。"""
    assert client.get("/questions").status_code == 200


def test_diagnostics():
    """/diagnostics 返回含 status 字段且不含 Key。"""
    r = client.get("/diagnostics")
    assert r.status_code == 200
    body = r.json()
    assert "status" in body
    assert "sk-" not in json.dumps(body)


def test_runs_list():
    """GET /runs 返回 runs 列表。"""
    r = client.get("/runs")
    assert r.status_code == 200
    assert "runs" in r.json()


def test_no_submission_routes():
    """路由表中不含 submission/technical_solution/demo_script 主流程接口。"""
    paths = _runtime_route_paths(app.routes)
    openapi_paths = set(app.openapi()["paths"])
    assert openapi_paths, "OpenAPI route set unexpectedly empty"
    assert openapi_paths.issubset(set(paths))
    joined = " ".join(paths)
    for token in ("submission", "technical_solution", "demo_script", "bundle"):
        assert token not in joined, f"路由仍含 {token}"
    # 保留核心导出路由。
    assert any("/export/markdown" in p for p in paths)
    assert any("/export/pdf" in p for p in paths)
    assert any("/files/{file_name}" in p for p in paths)


def test_legacy_route_enumeration_fails_closed_on_pathless_node(monkeypatch):
    """旧版 fallback 不得静默跳过缺少 path 的路由树节点。"""

    class PathRoute:
        path = "/health"

    class PathlessRoute:
        pass

    monkeypatch.setattr(
        sys.modules[__name__],
        "_iter_route_contexts",
        None,
    )
    with pytest.raises(
        AssertionError,
        match="UNSUPPORTED_ROUTE_TREE_WITHOUT_PUBLIC_ITERATOR",
    ):
        _runtime_route_paths([PathRoute(), PathlessRoute()])
