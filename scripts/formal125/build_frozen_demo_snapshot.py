"""Build a sanitized deployment snapshot from the immutable Formal 125 RC."""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.formal125 import REQUIRED_RESULT_FILES
from app.formal125.continuous_fast import scan_text_for_secrets
from app.formal125.frozen_demo import OFFICIAL_IDS, sha256_file, snapshot_digest, snapshot_secret_hits
from app.formal125.hashes import sha256_canonical_json
from app.formal125.review_rc import ORIGINAL_CANDIDATE, candidate_fingerprint


SOURCE_RC = Path(r"D:\SAGE125_Local_Runs\formal_125_release_candidate_20260822-201733")
DEST = ROOT / "deployment" / "frozen_rc"
ABS_RE = re.compile(r"[A-Za-z]:\\[^\s\"']+|/Users/[^/\s\"']+")
TOP_COPY = (
    "manifest.json",
    "index.json",
    "index.md",
    "summary_report.json",
    "manual_review_summary.json",
    "failure_and_partial_report.json",
    "provider_call_inventory.json",
    "budget_report.json",
    "domain_summary.json",
    "reproduction.md",
    "release_notes.md",
    "package_manifest.json",
    "checksums.sha256",
    "CANDIDATE_STATUS.json",
    "remediation_summary.json",
)
SKIP_HINTS = ("DASHSCOPE_API_KEY=", "WORKSPACE_ID=", "Authorization:", "Bearer ")


def _copy_text_redacted(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.suffix.lower() in {".pdf", ".png", ".jpg", ".svg"}:
        shutil.copy2(src, dest)
        return
    text = src.read_text(encoding="utf-8", errors="ignore")
    text = ABS_RE.sub("[local-path-redacted]", text)
    dest.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build() -> dict[str, object]:
    if candidate_fingerprint(ORIGINAL_CANDIDATE) != "5c6afaa358072c9a6c71c2bb062d7d952267f5fb9a51153b180bb583cb83372d":
        raise RuntimeError("original candidate fingerprint drifted; abort snapshot")
    if DEST.exists():
        shutil.rmtree(DEST)
    DEST.mkdir(parents=True)
    extras = ("manual_disposition.json",)
    for qid in OFFICIAL_IDS:
        src = SOURCE_RC / qid
        dest = DEST / qid
        dest.mkdir()
        for name in REQUIRED_RESULT_FILES + extras:
            path = src / name
            if path.is_file():
                _copy_text_redacted(path, dest / name)
    for name in TOP_COPY:
        path = SOURCE_RC / name
        if path.is_file():
            _copy_text_redacted(path, DEST / name)
    review_src = SOURCE_RC / "manual_review_24"
    if review_src.is_dir():
        for path in review_src.rglob("manual_review_decision.json"):
            _copy_text_redacted(path, DEST / "manual_review_24" / path.parent.name / path.name)
    flagship = DEST / "flagship"
    flagship.mkdir()
    repo = ROOT
    ablation = json.loads(
        (
            repo
            / "docs/reproducibility/ablations/Q028/verified/Q028-ACTUAL-ABLATION-01-FREEZE-20260821-133128/ablation_conclusion.json"
        ).read_text(encoding="utf-8")
    )
    pointer = json.loads((repo / "docs/modules/T05/canonical/canonical_pointer.json").read_text(encoding="utf-8"))
    pointer["final_path"] = "[canonical-final-redacted-local-path]"
    stop = json.loads((repo / "docs/modules/T05/round2/review/stop_reason.json").read_text(encoding="utf-8"))
    r1 = json.loads((repo / "docs/modules/T05/round1/artifacts/metrics-malignant-recall.json").read_text(encoding="utf-8"))
    r2 = json.loads((repo / "docs/modules/T05/round2/artifacts/metrics-malignant-recall.json").read_text(encoding="utf-8"))
    closure = json.loads((repo / "docs/modules/T05/round2/review/issue_closure.json").read_text(encoding="utf-8"))
    _write_json(
        flagship / "q028_flagship_summary.json",
        {
            "question_id": "Q028",
            "canonical_pointer": pointer,
            "round1_malignant_recall": r1.get("metric", {}).get("value"),
            "round2_malignant_recall": r2.get("metric", {}).get("value"),
            "stop_reason": stop,
            "issue_closure": {
                "unresolved_p0": stop.get("unresolved_p0"),
                "unresolved_p1": stop.get("unresolved_p1"),
                "keys": list(closure)[:12] if isinstance(closure, dict) else [],
            },
            "scientific_limitation": stop.get("scientific_limitation"),
        },
    )
    _write_json(flagship / "q028_ablation_summary.json", ablation)
    hits = snapshot_secret_hits(DEST)
    if hits:
        raise RuntimeError(f"secret scan hits in snapshot: {hits}")
    files = [p for p in DEST.rglob("*") if p.is_file()]
    total = sum(p.stat().st_size for p in files)
    max_file = max(files, key=lambda p: p.stat().st_size)
    digest = snapshot_digest(DEST)
    report = {
        "DEPLOYMENT_RC_FILE_COUNT": len(files),
        "DEPLOYMENT_RC_SIZE_MIB": round(total / 1024 / 1024, 2),
        "DEPLOYMENT_RC_MAX_FILE_MIB": round(max_file.stat().st_size / 1024 / 1024, 2),
        "DEPLOYMENT_RC_MAX_FILE": max_file.relative_to(DEST).as_posix(),
        "DEPLOYMENT_RC_SHA256": digest,
        "DEPLOYMENT_SECRET_HIT_COUNT": hits,
        "SOURCE_RC": str(SOURCE_RC),
        "DEST": str(DEST),
    }
    _write_json(DEST / "deployment_snapshot_manifest.json", report)
    _write_json(ROOT / "docs" / "deploy" / "frozen_rc_digest.json", report)
    return report


def main() -> int:
    report = build()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
