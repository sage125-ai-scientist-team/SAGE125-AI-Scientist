"""T01 EvidenceBundle SQLite store / read_port 最小验收。"""

from __future__ import annotations

import json
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest

from app.contracts.evidence import (
    ClaimEvidenceLink,
    EvidenceBundle,
    EvidenceCardContract,
)
from app.evidence.read_port import (
    get_evidence_bundle,
    mark_evidence_failed,
    mark_evidence_pending,
    save_evidence_bundle,
)
from app.evidence.store import EvidencePortError, SqliteEvidenceBundleStore


def _card(eid: str = "EV-1") -> EvidenceCardContract:
    return EvidenceCardContract(
        evidence_id=eid,
        source_id="src-1",
        source_type="paper",
        title="Soil interface study",
        quoted_text="Soils constitute a primordial compartment of terrestrial ecosystems.",
        locator={"section": "Introduction", "page": 1},
        authors=["Ada"],
        year=2007,
        doi="10.1371/journal.pone.0001248",
        content_hash="sha256:abc",
        domain="ecology",
        verification_status="valid",
    )


def _bundle(bundle_id: str = "B-1", eid: str = "EV-1") -> EvidenceBundle:
    return EvidenceBundle(
        bundle_id=bundle_id,
        evidences=[_card(eid)],
        links=[
            ClaimEvidenceLink(
                claim_id="C-1",
                evidence_id=eid,
                relation="supports",
                confidence=0.9,
                claim_domain="ecology",
            )
        ],
        token_budget=8000,
        truncated=False,
    )


def test_restart_recovery(tmp_path: Path) -> None:
    """重启等价：新 store 实例指向同一文件应可读。"""
    db = tmp_path / "e.sqlite3"
    store_a = SqliteEvidenceBundleStore(db)
    save_evidence_bundle(
        run_id="run-1",
        question_id="Q001",
        bundle=_bundle(),
        store=store_a,
    )
    store_b = SqliteEvidenceBundleStore(db)
    got = get_evidence_bundle(run_id="run-1", question_id="Q001", store=store_b)
    assert got.evidences[0].quoted_text.startswith("Soils constitute")
    assert got.links[0].relation == "supports"


def test_cross_question_fail_closed(tmp_path: Path) -> None:
    """跨 question 不得串读。"""
    store = SqliteEvidenceBundleStore(tmp_path / "e.sqlite3")
    save_evidence_bundle(
        run_id="run-1",
        question_id="Q001",
        bundle=_bundle(),
        store=store,
    )
    with pytest.raises(EvidencePortError) as exc:
        get_evidence_bundle(run_id="run-1", question_id="Q002", store=store)
    assert exc.value.category == "not_found"


def test_idempotent_and_conflict(tmp_path: Path) -> None:
    """同 payload 幂等；不同 payload 冲突。"""
    store = SqliteEvidenceBundleStore(tmp_path / "e.sqlite3")
    b1 = _bundle("B-1")
    save_evidence_bundle(run_id="run-1", question_id="Q001", bundle=b1, store=store)
    again = save_evidence_bundle(
        run_id="run-1", question_id="Q001", bundle=b1, store=store
    )
    assert again.bundle_id == "B-1"
    b2 = _bundle("B-2")
    with pytest.raises(EvidencePortError) as exc:
        save_evidence_bundle(
            run_id="run-1", question_id="Q001", bundle=b2, store=store
        )
    assert exc.value.category == "conflict"


def test_hash_tamper_rejected(tmp_path: Path) -> None:
    """篡改 payload 后 get 必须 invalid_contract。"""
    db = tmp_path / "e.sqlite3"
    store = SqliteEvidenceBundleStore(db)
    save_evidence_bundle(
        run_id="run-1", question_id="Q001", bundle=_bundle(), store=store
    )
    conn = sqlite3.connect(str(db))
    row = conn.execute(
        "SELECT payload_json FROM evidence_bundles WHERE run_id=? AND question_id=?",
        ("run-1", "Q001"),
    ).fetchone()
    assert row is not None
    tampered = json.loads(row[0])
    tampered["evidences"][0]["quoted_text"] = "TAMPERED QUOTE TEXT LONG ENOUGH"
    conn.execute(
        "UPDATE evidence_bundles SET payload_json=? WHERE run_id=? AND question_id=?",
        (json.dumps(tampered, ensure_ascii=False), "run-1", "Q001"),
    )
    conn.commit()
    conn.close()
    with pytest.raises(EvidencePortError) as exc:
        get_evidence_bundle(run_id="run-1", question_id="Q001", store=store)
    assert exc.value.category == "invalid_contract"


def test_pending_failed_not_found_distinct(tmp_path: Path) -> None:
    """pending / failed / not_found 语义区分。"""
    store = SqliteEvidenceBundleStore(tmp_path / "e.sqlite3")
    with pytest.raises(EvidencePortError) as e0:
        get_evidence_bundle(run_id="run-x", question_id="Qx", store=store)
    assert e0.value.category == "not_found"

    mark_evidence_pending(run_id="run-1", question_id="Q001", store=store)
    with pytest.raises(EvidencePortError) as e1:
        get_evidence_bundle(run_id="run-1", question_id="Q001", store=store)
    assert e1.value.category == "not_ready"

    mark_evidence_failed(
        run_id="run-1",
        question_id="Q001",
        failure_code="BUILD_FAILED",
        failure_summary="upstream empty hits",
        store=store,
    )
    with pytest.raises(EvidencePortError) as e2:
        get_evidence_bundle(run_id="run-1", question_id="Q001", store=store)
    assert e2.value.category == "non_retryable_upstream_failure"
    assert "BUILD_FAILED" in str(e2.value)


def test_five_way_concurrency_same_payload(tmp_path: Path) -> None:
    """五并发同 payload 不得互相破坏。"""
    store = SqliteEvidenceBundleStore(tmp_path / "e.sqlite3")
    bundle = _bundle()
    errors: list[BaseException] = []

    def _save() -> None:
        try:
            save_evidence_bundle(
                run_id="run-c",
                question_id="Q009",
                bundle=bundle,
                store=store,
            )
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=_save) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert errors == []
    got = get_evidence_bundle(run_id="run-c", question_id="Q009", store=store)
    assert got.evidences[0].content_hash == "sha256:abc"


def test_five_way_concurrency_mixed_payload_no_silent_merge(tmp_path: Path) -> None:
    """五并发不同 payload：最终要么单一 winner，要么 conflict，不得混写。"""
    store = SqliteEvidenceBundleStore(tmp_path / "e.sqlite3")
    outcomes: list[str] = []

    def _save(i: int) -> None:
        try:
            save_evidence_bundle(
                run_id="run-m",
                question_id="Q010",
                bundle=_bundle(bundle_id=f"B-{i}", eid=f"EV-{i}"),
                store=store,
            )
            outcomes.append("ok")
        except EvidencePortError as exc:
            outcomes.append(exc.category)

    with ThreadPoolExecutor(max_workers=5) as pool:
        futs = [pool.submit(_save, i) for i in range(5)]
        for f in as_completed(futs):
            f.result()
    assert outcomes.count("ok") >= 1
    assert all(x in {"ok", "conflict"} for x in outcomes)
    got = get_evidence_bundle(run_id="run-m", question_id="Q010", store=store)
    assert len(got.evidences) == 1
    assert got.bundle_id.startswith("B-")


def test_fields_preserved(tmp_path: Path) -> None:
    """quote/locator/relation/confidence/hash/truncation 不丢失。"""
    store = SqliteEvidenceBundleStore(tmp_path / "e.sqlite3")
    bundle = EvidenceBundle(
        bundle_id="B-t",
        evidences=[_card()],
        links=[
            ClaimEvidenceLink(
                claim_id="C-1",
                evidence_id="EV-1",
                relation="supports",
                confidence=0.77,
                claim_domain="ecology",
            )
        ],
        truncated=True,
        truncation_reason="token_budget",
    )
    save_evidence_bundle(
        run_id="run-1", question_id="Q001", bundle=bundle, store=store
    )
    got = get_evidence_bundle(run_id="run-1", question_id="Q001", store=store)
    assert got.evidences[0].quoted_text.startswith("Soils")
    assert got.evidences[0].locator["section"] == "Introduction"
    assert got.links[0].relation == "supports"
    assert got.links[0].confidence == 0.77
    assert got.evidences[0].content_hash == "sha256:abc"
    assert got.truncated is True
    assert got.truncation_reason == "token_budget"


def test_no_absolute_paths_in_errors(tmp_path: Path) -> None:
    """错误消息不得回显绝对路径。"""
    store = SqliteEvidenceBundleStore(tmp_path / "e.sqlite3")
    with pytest.raises(EvidencePortError) as exc:
        get_evidence_bundle(run_id="missing", question_id="Qx", store=store)
    msg = str(exc.value)
    assert ":\\" not in msg
    assert "/Users/" not in msg
    assert str(tmp_path) not in msg


def test_invalid_identity_tokens(tmp_path: Path) -> None:
    store = SqliteEvidenceBundleStore(tmp_path / "e.sqlite3")
    with pytest.raises(EvidencePortError) as exc:
        get_evidence_bundle(run_id="../x", question_id="Q1", store=store)
    assert exc.value.category == "invalid_contract"
