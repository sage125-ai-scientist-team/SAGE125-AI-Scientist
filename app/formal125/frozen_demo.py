"""Read-only frozen Formal 125 Release Candidate demo. No provider calls."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Mapping

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

T09_DOMAIN_REPRESENTATIVES: tuple[tuple[str, str, str], ...] = (
    ("Q001", "mathematics", "Mathematical Sciences"),
    ("Q069", "physics", "Physics"),
    ("Q003", "chemistry", "Chemistry"),
    ("Q026", "biology", "Biology"),
    ("Q013", "medicine", "Medicine & Health"),
    ("Q109", "earth_science", "Ecology"),
    ("Q091", "computer_science", "Information Science"),
    ("Q089", "materials", "Engineering & Materials Science"),
    ("Q046", "astronomy", "Astronomy"),
    ("Q095", "neuroscience", "Neuroscience"),
    ("Q107", "climate", "Ecology"),
    ("Q088", "engineering", "Engineering & Materials Science"),
)
SECRET_RE = re.compile(
    r"(?i)(?:api[_-]?key|authorization|bearer|password|secret)\s*[:=]\s*\S+|sk-[A-Za-z0-9]{8,}|workspace_id\s*[:=]\s*\S+"
)


def scan_text_for_secrets(text: str) -> int:
    return 1 if SECRET_RE.search(text or "") else 0


OFFICIAL_IDS = tuple(f"Q{i:03d}" for i in range(1, 126))
DOWNLOAD_ALLOWLIST = frozenset(
    {
        "result.pdf",
        "result.md",
        "result.json",
        "evidence_cards.json",
        "validation.json",
        "package_manifest.json",
        "provider_audit.json",
        "checksums.sha256",
        "manual_disposition.json",
    }
)
WIN_ABS = re.compile(r"[A-Za-z]:\\[^\s\"']+")
POSIX_HOME = re.compile(r"/Users/[^/\s\"']+")
SECRET_HINTS = ("DASHSCOPE_API_KEY", "WORKSPACE_ID", "Authorization", "Bearer ", "sk-")
PUBLIC_RUN_DENIED = "演示环境仅展示已冻结结果，正式运行接口已关闭。"


class FrozenDemoError(RuntimeError):
    """Raised when the frozen RC snapshot cannot be served."""


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_rc_root() -> Path:
    configured = os.environ.get("FORMAL_125_RC_ROOT", "").strip()
    if configured:
        return Path(configured)
    relative = os.environ.get("RC_MANIFEST_RELATIVE_PATH", "deployment/frozen_rc/manifest.json").strip()
    manifest = Path(relative)
    if not manifest.is_absolute():
        manifest = repo_root() / manifest
    return manifest.parent


def load_json(path: Path) -> Any:
    if not path.is_file():
        raise FrozenDemoError(f"required file missing: {path.name}")
    return json.loads(path.read_text(encoding="utf-8"))


def official_question_id(raw: str) -> str:
    qid = str(raw or "").strip().upper()
    if qid not in OFFICIAL_IDS:
        raise HTTPException(status_code=404, detail="question_id not in Q001-Q125")
    return qid


def question_dir(root: Path, question_id: str) -> Path:
    path = (root / question_id).resolve()
    if path.parent != root.resolve() or not path.is_dir():
        raise HTTPException(status_code=404, detail="question directory missing")
    return path


def public_env() -> dict[str, Any]:
    return {
        "APP_ENV": os.environ.get("APP_ENV", "competition_demo"),
        "DEMO_MODE": os.environ.get("DEMO_MODE", "FROZEN_RELEASE_CANDIDATE"),
        "FORMAL_125_READ_ONLY": True,
        "ALLOW_PUBLIC_ACTUAL_RUN": False,
        "ALLOW_PUBLIC_PROVIDER_CALL": False,
        "PUBLIC_FEEDBACK_WRITE_ENABLED": False,
        "public_run_message": PUBLIC_RUN_DENIED,
    }


def snapshot_secret_hits(root: Path) -> int:
    hits = 0
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() in {".pdf", ".png", ".jpg", ".svg"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        hits += scan_text_for_secrets(text)
        if any(hint in text for hint in SECRET_HINTS) and "key_masked" not in text:
            if re.search(r"(?i)(api[_-]?key|authorization)\s*[:=]\s*\S+", text):
                hits += 1
    return hits


def verify_snapshot(root: Path) -> dict[str, Any]:
    if not root.is_dir():
        raise FrozenDemoError("frozen RC root does not exist")
    manifest = load_json(root / "manifest.json")
    if int(manifest.get("total") or 0) != 125:
        raise FrozenDemoError("manifest.total is not 125")
    ids = list(manifest.get("question_ids") or [])
    if ids != list(OFFICIAL_IDS):
        raise FrozenDemoError("question_ids are not Q001-Q125 unique consecutive")
    missing = [qid for qid in OFFICIAL_IDS if not (root / qid).is_dir()]
    if missing:
        raise FrozenDemoError(f"missing question directories: {missing[:8]}")
    return manifest


def latest_run(root: Path | None = None) -> dict[str, Any]:
    root = root or resolve_rc_root()
    manifest = verify_snapshot(root)
    summary = load_json(root / "summary_report.json")
    review = load_json(root / "manual_review_summary.json") if (root / "manual_review_summary.json").is_file() else {}
    inventory = load_json(root / "provider_call_inventory.json") if (root / "provider_call_inventory.json").is_file() else {}
    return {
        "total": 125,
        "status_counts": summary.get("status_counts") or manifest.get("status_counts"),
        "FORMAL_125_RC_READY": True,
        "FINAL_SUBMISSION_READY": False,
        "manual_review": review,
        "provider_inventory_public": {
            "project_provider_calls": inventory.get("project_provider_calls_after")
            or inventory.get("project_provider_calls_before"),
            "new_remediation_provider_calls": inventory.get("new_remediation_provider_calls", 0),
            "openrouter_calls": inventory.get("openrouter_calls", 0),
            "mock_calls": inventory.get("mock_calls", 0),
            "secrets_included": False,
        },
        "manual_review_formation": (
            "队长基于当前正式状态和既有自动质量门，对冻结的 24 题抽查集"
            "进行状态映射式人工接受；未新增模型修复。"
        ),
        "read_only": True,
        **public_env(),
    }


def latest_domains() -> dict[str, Any]:
    mapping = [
        {"question_id": qid, "t09_domain_id": domain, "booklet_domain": booklet}
        for qid, domain, booklet in T09_DOMAIN_REPRESENTATIVES
    ]
    return {"count": len(mapping), "domains": mapping, "note": "12 booklet domain representatives"}


def _question_card(root: Path, qid: str) -> dict[str, Any]:
    qdir = question_dir(root, qid)
    manifest = load_json(qdir / "package_manifest.json")
    result = load_json(qdir / "result.json") if (qdir / "result.json").is_file() else {}
    validation = load_json(qdir / "validation.json") if (qdir / "validation.json").is_file() else {}
    cards = load_json(qdir / "evidence_cards.json") if (qdir / "evidence_cards.json").is_file() else []
    disposition = None
    if (qdir / "manual_disposition.json").is_file():
        disposition = load_json(qdir / "manual_disposition.json")
    return {
        "question_id": qid,
        "status": manifest.get("status"),
        "paper_title": result.get("paper_title") or result.get("input_question"),
        "official_title": result.get("input_question") or result.get("official_title"),
        "p0_count": validation.get("p0_count", 0),
        "p1_count": validation.get("p1_count", 0),
        "evidence_count": len(cards) if isinstance(cards, list) else 0,
        "provider_calls": manifest.get("provider_calls") or 0,
        "pdf_present": (qdir / "result.pdf").is_file(),
        "md_present": (qdir / "result.md").is_file(),
        "json_present": (qdir / "result.json").is_file(),
        "manual_disposition": (disposition or {}).get("decision"),
        "block_code": manifest.get("block_code") or result.get("block_code"),
    }


def latest_questions(root: Path | None = None) -> dict[str, Any]:
    root = root or resolve_rc_root()
    verify_snapshot(root)
    items = [_question_card(root, qid) for qid in OFFICIAL_IDS]
    return {"count": len(items), "questions": items}


def latest_question(question_id: str, root: Path | None = None) -> dict[str, Any]:
    root = root or resolve_rc_root()
    qid = official_question_id(question_id)
    card = _question_card(root, qid)
    qdir = question_dir(root, qid)
    result = load_json(qdir / "result.json") if (qdir / "result.json").is_file() else {}
    cards = load_json(qdir / "evidence_cards.json") if (qdir / "evidence_cards.json").is_file() else []
    validation = load_json(qdir / "validation.json") if (qdir / "validation.json").is_file() else {}
    safe_cards = []
    if isinstance(cards, list):
        for item in cards:
            if not isinstance(item, dict):
                continue
            safe_cards.append(
                {
                    "evidence_id": item.get("evidence_id") or item.get("id"),
                    "quote": item.get("quote") or item.get("quoted_text"),
                    "locator": item.get("locator") or item.get("reliability_note"),
                    "source_type": item.get("source_type"),
                    "doi": item.get("doi"),
                    "url": item.get("url") or item.get("landing_url"),
                    "title": item.get("title") or item.get("source_title"),
                }
            )
    return {
        **card,
        "abstract": result.get("abstract") or result.get("paper_abstract"),
        "hypotheses": result.get("generated_hypotheses") or result.get("hypotheses") or [],
        "research_plan": result.get("research_plan") or result.get("experiment_plan"),
        "reviewer": result.get("reviewer_feedback") or result.get("scientific_review"),
        "revision_context": result.get("revision_context"),
        "evidence_cards": safe_cards,
        "validation": {
            "p0_count": validation.get("p0_count", 0),
            "p1_count": validation.get("p1_count", 0),
            "blocked": validation.get("blocked"),
        },
        "downloads": {
            "pdf": f"/downloads/{qid}/result.pdf",
            "md": f"/downloads/{qid}/result.md",
            "json": f"/downloads/{qid}/result.json",
        },
        "public_run_message": PUBLIC_RUN_DENIED,
    }


def manual_review(root: Path | None = None) -> dict[str, Any]:
    root = root or resolve_rc_root()
    payload = load_json(root / "manual_review_summary.json")
    payload["formation"] = (
        "队长基于当前正式状态和既有自动质量门，对冻结的 24 题抽查集"
        "进行状态映射式人工接受；未新增模型修复。"
    )
    payload["not_independent_expert_review"] = True
    return payload


def flagship_q028(root: Path | None = None) -> dict[str, Any]:
    root = root or resolve_rc_root()
    detail = latest_question("Q028", root)
    extras = root / "flagship"
    summary = load_json(extras / "q028_flagship_summary.json") if (extras / "q028_flagship_summary.json").is_file() else {}
    return {
        "question_id": "Q028",
        "available": True,
        "detail": detail,
        "flagship": summary,
        "disclaimer": (
            "Q028 WDBC 是受控二分类演示，不构成治愈癌症、临床验证或医疗建议。"
        ),
    }


def ablation_q028(root: Path | None = None) -> dict[str, Any]:
    root = root or resolve_rc_root()
    extras = root / "flagship"
    payload = load_json(extras / "q028_ablation_summary.json") if (extras / "q028_ablation_summary.json").is_file() else {}
    return {
        "question_id": "Q028",
        "available": bool(payload),
        "conclusion": payload.get("REVIEWER_EFFECT_RESULT") or "TRACEABILITY_ONLY_GAIN",
        "quality_gain": payload.get("quality_gain", False),
        "traceability_gain": payload.get("traceability_gain", True),
        "summary": payload,
        "note": "该案例质量指标无提升，Reviewer 收益主要体现在可审计性。",
    }


def download_file(question_id: str, filename: str, root: Path | None = None) -> FileResponse:
    root = root or resolve_rc_root()
    qid = official_question_id(question_id)
    name = Path(filename).name
    if name != filename or name not in DOWNLOAD_ALLOWLIST:
        raise HTTPException(status_code=404, detail="download not allowed")
    path = (question_dir(root, qid) / name).resolve()
    if path.parent != question_dir(root, qid) or not path.is_file():
        raise HTTPException(status_code=404, detail="file missing")
    media = "application/pdf" if name.endswith(".pdf") else "application/json" if name.endswith(".json") else "text/markdown"
    return FileResponse(path, media_type=media, filename=name)


def denied_write(_: Request) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={
            "ok": False,
            "code": "PUBLIC_ACTUAL_RUN_DISABLED",
            "message": PUBLIC_RUN_DENIED,
            "ALLOW_PUBLIC_ACTUAL_RUN": False,
        },
    )


def create_demo_api() -> FastAPI:
    root = resolve_rc_root()
    verify_snapshot(root)
    application = FastAPI(
        title="SAGE125 Frozen Formal 125 API",
        description="Read-only competition demo. Frozen RC only. No provider calls.",
        version="final-demo",
    )
    origins = [item.strip() for item in os.environ.get("CORS_ALLOW_ORIGINS", "").split(",") if item.strip()]
    if origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_methods=["GET", "HEAD", "OPTIONS"],
            allow_headers=["*"],
        )

    @application.get("/health")
    def health() -> dict[str, Any]:
        manifest = verify_snapshot(root)
        return {
            "status": "ok",
            "service": "sage125-final-api",
            "questions_count": 125,
            "status_counts": manifest.get("status_counts"),
            "read_only": True,
            "provider_calls_enabled": False,
            **public_env(),
        }

    @application.get("/formal-runs/latest")
    def formal_latest() -> dict[str, Any]:
        return latest_run(root)

    @application.get("/formal-runs/latest/domains")
    def formal_domains() -> dict[str, Any]:
        return latest_domains()

    @application.get("/formal-runs/latest/questions")
    def formal_questions() -> dict[str, Any]:
        return latest_questions(root)

    @application.get("/formal-runs/latest/questions/Q028/flagship")
    def formal_flagship() -> dict[str, Any]:
        return flagship_q028(root)

    @application.get("/formal-runs/latest/questions/{question_id}")
    def formal_question(question_id: str) -> dict[str, Any]:
        return latest_question(question_id, root)

    @application.get("/formal-runs/latest/manual-review")
    def formal_review() -> dict[str, Any]:
        return manual_review(root)

    @application.get("/formal-runs/latest/ablation")
    def formal_ablation() -> dict[str, Any]:
        return ablation_q028(root)

    @application.get("/downloads/{question_id}/{filename}")
    def formal_download(question_id: str, filename: str) -> FileResponse:
        return download_file(question_id, filename, root)

    @application.middleware("http")
    async def block_writes(request: Request, call_next):
        if request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
            return denied_write(request)
        return await call_next(request)

    return application


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def snapshot_digest(root: Path) -> str:
    payload = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root).as_posix()
        payload.append(f"{sha256_file(path)}  {rel}")
    return hashlib.sha256("\n".join(payload).encode("utf-8")).hexdigest()
