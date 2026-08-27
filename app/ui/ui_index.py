# -*- coding: utf-8 -*-
"""轻量 UI 索引（125 题清单 + 每题状态摘要）。

对应队长任务 CAPTAIN-LOCAL-SAGE125-FIXED-OPEN-SOURCE-UI-RUNTIME-PERFORMANCE-05
第十四节。索引文件只保存以下十个字段：

    question_id, title, domain, status, evidence_count, hypothesis_count,
    plan_status, updated_at, result_path, digest

首页与工作区概览只应读取这份轻量索引来展示「125 题中哪些已有运行/证据」这类
汇总信息；用户真正点击某一道题后，才通过既有的 `state`/`api_client` 读取该题
完整结果（`report.json`/`evidence_cards.json`/`agent_trace.json` 等）。

索引重建时机（不得每次 Streamlit rerun 都重建）：
    - 索引文件不存在（服务首次启动）；
    - `questions_125.json`（题库 manifest）的 mtime 发生变化；
    - 用户主动调用 `build_ui_question_index(force=True)`（对应「用户主动刷新」）。

注意：本模块本身不依赖 Streamlit，可独立于 UI 进程运行/测试
（例如未来接入「服务启动」「新结果完成」钩子，或单独的 CLI 重建脚本）。
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.ui.api_client import PROJECT_ROOT, QUESTIONS_PATH
from app.ui.results_root import resolve_results_root
from app.ui.run_browser import list_runs as _list_exports_runs

UI_INDEX_PATH = PROJECT_ROOT / "data" / "ui" / "ui_question_index.json"

# 默认扫描的 exports/ 运行数量上限：125 题 + 少量重跑余量，
# 一次性扫描即可覆盖全部题目的「最近一次运行」，无需对每道题单独查询。
_DEFAULT_RUNS_SCAN_LIMIT = 400


def _digest(payload: dict[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_questions() -> list[dict]:
    try:
        from app.catalog.official import load_official_catalog

        catalog = load_official_catalog()
        return [item.as_api_item(catalog.get_catalog_digest()) for item in catalog.list_questions()]
    except Exception:
        if not QUESTIONS_PATH.exists():
            return []
        try:
            return json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []


def _questions_mtime() -> float | None:
    try:
        return QUESTIONS_PATH.stat().st_mtime
    except OSError:
        return None


def build_ui_question_index(*, runs_scan_limit: int = _DEFAULT_RUNS_SCAN_LIMIT) -> dict[str, Any]:
    """重建轻量 UI 索引并写入磁盘；返回索引 dict。

    一次性扫描 `exports/`（复用既有 `run_browser.list_runs`，不重复实现目录
    遍历逻辑），按 question_id 归并到「该题最近一次运行」，再和 125 题清单
    (`questions_125.json`) 做左连接。不读取 PDF、不计算全量 SHA-256、
    不打开 provider_audit/agent_trace（那些属于「点击后按需加载完整结果」的
    范畴，不属于首屏轻量索引）。
    """
    questions = _load_questions()
    resolved = resolve_results_root()
    runs = _list_exports_runs(limit=runs_scan_limit)

    latest_by_qid: dict[str, dict] = {}
    for run in runs:
        qid = str(run.get("question_id") or "").strip()
        if qid and qid not in latest_by_qid:
            latest_by_qid[qid] = run

    items: list[dict[str, Any]] = []
    for q in questions:
        qid = str(q.get("question_id") or q.get("id") or "").strip()
        run = latest_by_qid.get(qid)
        official_result = None
        if resolved.results_root is not None:
            candidate = resolved.results_root / qid / "result.json"
            if candidate.exists():
                official_result = candidate
        if official_result is not None:
            result_path = str(official_result)
            if run:
                status = str(run.get("validation_status") or ("mock" if run.get("mock") else "completed") or "draft")
                evidence_count = int(run.get("evidence_count") or 0)
                updated_at = run.get("created_at")
            else:
                status = "has_result"
                evidence_count = None
                updated_at = None
        elif run:
            status = str(run.get("validation_status") or ("mock" if run.get("mock") else "completed") or "draft")
            evidence_count = int(run.get("evidence_count") or 0)
            updated_at = run.get("created_at")
            result_path = run.get("report_rel_path")
        else:
            status = "not_started"
            evidence_count = 0
            updated_at = None
            result_path = None
        item = {
            "question_id": qid,
            "title": q.get("title_en") or q.get("question") or q.get("title") or "",
            "title_en": q.get("title_en") or q.get("question") or q.get("title") or "",
            "title_zh": q.get("title_zh") or "",
            "domain": q.get("domain"),
            "catalog_digest": q.get("catalog_digest") or "",
            "status": status,
            "evidence_count": evidence_count,
            # 候选假设数量需要打开 report.json 读取 generated_hypotheses，
            # 属于「完整结果」范畴；轻量索引阶段保持 None（前端显示「—」），
            # 不为了填充这一个字段而多做一次磁盘 IO。
            "hypothesis_count": None,
            "plan_status": status,
            "updated_at": updated_at,
            "result_path": result_path,
        }
        item["digest"] = _digest(item)
        items.append(item)

    try:
        from app.catalog.official import get_catalog_digest

        catalog_digest = get_catalog_digest()
    except Exception:
        catalog_digest = ""
    index = {
        "schema_version": "1",
        "catalog_source": "official",
        "catalog_digest": catalog_digest,
        "question_count": len(items),
        "generated_at": _now_iso(),
        "meta": {
            "questions_manifest_mtime": _questions_mtime(),
            "question_count": len(items),
            "runs_scanned": len(runs),
            "built_at": _now_iso(),
            "catalog_source": "official",
            "catalog_digest": catalog_digest,
        },
        "questions": items,
    }
    UI_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    UI_INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return index


def load_ui_question_index(*, force_rebuild: bool = False) -> dict[str, Any]:
    """读取磁盘上的轻量索引；缺失或题库 manifest mtime 变化时才重建。

    `force_rebuild=True` 对应「用户主动刷新」；正常路径下只做一次磁盘读取，
    不遍历 125 题目录、不重新扫描 exports/。
    """
    if not force_rebuild and UI_INDEX_PATH.exists():
        try:
            index = json.loads(UI_INDEX_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            index = None
        if isinstance(index, dict):
            recorded_mtime = (index.get("meta") or {}).get("questions_manifest_mtime")
            if recorded_mtime == _questions_mtime():
                return index
    return build_ui_question_index()


def question_status_map(index: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    """把索引转成 {question_id: item} 形式，方便页面按题号查状态。"""
    idx = index if index is not None else load_ui_question_index()
    return {str(item.get("question_id")): item for item in idx.get("questions", [])}
