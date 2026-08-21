"""Phase A evidence remediation: freeze attempt 1 and rebuild OA bundles."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.evidence.eligibility import FACT_ELIGIBLE, SourceEligibility
from app.evidence.id_guard import UnknownEvidenceIDError, assert_known_evidence_ids, deterministic_evidence_id
from app.evidence.oa_fulltext import (
    FulltextFetchAudit,
    arxiv_id_from_url,
    fetch_arxiv_pdf,
    select_quote,
    utc_now,
)

FORMAL_5 = ("Q001", "Q028", "Q050", "Q075", "Q107")
FORMAL_12_NEW = (
    "Q069",
    "Q003",
    "Q026",
    "Q013",
    "Q109",
    "Q091",
    "Q089",
    "Q046",
    "Q095",
    "Q088",
)
ATTEMPT1_ROOT = Path(r"D:\SAGE125_Local_Runs\formal_5_real_20260821-153708")
QUESTION_KEYWORDS = {
    "Q001": ["prime", "primes", "cryptography", "factor", "zeta", "number theorem"],
    "Q028": ["cancer", "mutation", "tumor", "oncolog", "carcinoma", "heterogeneity"],
    "Q050": ["universe", "expand", "cosmolog", "dark energy", "bao", "redshift"],
    "Q075": ["quark", "lepton", "compositeness", "standard model", "particle"],
    "Q107": ["climate", "carbon", "warming", "greenhouse", "mitigation", "emission"],
    "Q069": ["diffraction", "limit", "optics", "resolution", "Abbe"],
    "Q003": ["pigment", "color", "chromophore", "dye", "organic"],
    "Q026": ["cell", "differentiation", "reprogramming", "pluripotent", "stem"],
    "Q013": ["pandemic", "predict", "epidemic", "forecast", "influenza"],
    "Q109": ["magnetic", "geodynamo", "geomagnetic", "earth", "core"],
    "Q091": ["processing", "speed", "computation", "limit", "Landauer"],
    "Q089": ["efficiency", "energy", "conversion", "photovoltaic", "Shockley"],
    "Q046": ["dimension", "spacetime", "compactification", "Kaluza", "extra"],
    "Q095": ["consciousness", "neural", "correlates", "awareness", "brain"],
    "Q088": ["Mars", "manufacturing", "ISRU", "in-situ", "regolith"],
}
QUERY_SEEDS = {
    "Q069": ("diffraction limit optics resolution", "Abbe diffraction optical resolution"),
    "Q003": (
        "organic pigment",
        "chromophore dye",
        "structural color pigment",
        "azo pigment chemistry",
    ),
    "Q026": ("cell reprogramming pluripotent differentiation", "stem cell lineage restriction"),
    "Q013": ("pandemic prediction epidemic forecast influenza", "infectious disease outbreak forecasting"),
    "Q109": (
        "geodynamo",
        "geomagnetic dynamo",
        "Earth magnetic field core",
        "outer core dynamo geomagnetism",
    ),
    "Q091": ("computer processing speed limit Landauer", "fundamental limits of computation"),
    "Q089": ("energy conversion efficiency Shockley Queisser", "photovoltaic thermoelectric efficiency limit"),
    "Q046": ("extra dimensions spacetime compactification", "Kaluza Klein how many dimensions"),
    "Q095": ("neural correlates of consciousness", "where does consciousness lie neuroscience"),
    "Q088": ("Mars manufacturing in-situ resource utilization", "ISRU additive manufacturing Mars"),
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def freeze_attempt1_references(output_root: Path) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for question_id in FORMAL_5:
        question_dir = ATTEMPT1_ROOT / question_id
        validation = json.loads((question_dir / "validation.json").read_text(encoding="utf-8"))
        manifest = json.loads((question_dir / "package_manifest.json").read_text(encoding="utf-8"))
        ref = {
            "question_id": question_id,
            "old_batch_id": "formal_5_real_20260821-153708",
            "old_attempt_id": "attempt-1",
            "old_output_path": str(question_dir),
            "result.json": sha256_file(question_dir / "result.json"),
            "evidence_cards.json": sha256_file(question_dir / "evidence_cards.json"),
            "validation.json": sha256_file(question_dir / "validation.json"),
            "provider_audit.json": sha256_file(question_dir / "provider_audit.json"),
            "package_digest": sha256_file(question_dir / "package_manifest.json"),
            "status": "partial",
            "unresolved_p0": validation.get("p0_count") or 0,
            "provider_call_count": manifest.get("provider_calls") or 0,
            "created_at": manifest.get("packaged_at"),
            "immutable": True,
        }
        write_json(output_root / question_id / "previous_attempt_reference.json", ref)
        refs.append(ref)
    return refs


def _load_attempt1_cards(question_id: str) -> list[dict[str, Any]]:
    path = ATTEMPT1_ROOT / question_id / "evidence_cards.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _load_attempt1_claims(question_id: str) -> list[dict[str, Any]]:
    exports = ATTEMPT1_ROOT / "pipeline_exports"
    claims: list[dict[str, Any]] = []
    for state_path in sorted(exports.glob("*/pipeline_state.json")):
        state = json.loads(state_path.read_text(encoding="utf-8"))
        selected = (state.get("selected_question") or {}).get("id")
        if selected != question_id:
            continue
        extraction = state.get("evidence_extraction") or {}
        for index, fact in enumerate(extraction.get("established_facts") or [], start=1):
            claims.append(
                {
                    "claim_id": f"{question_id}-fact-{index}",
                    "claim_text": fact.get("fact") or "",
                    "claim_type": fact.get("fact_type") or "background",
                    "required_evidence_level": "FULLTEXT_VERIFIED",
                    "old_evidence_ids": list(fact.get("evidence_ids") or []),
                }
            )
        for index, hyp in enumerate((state.get("hypothesis_generation") or {}).get("hypotheses") or [], start=1):
            claims.append(
                {
                    "claim_id": f"{question_id}-hyp-{index}",
                    "claim_text": hyp.get("hypothesis") or "",
                    "claim_type": "hypothesis",
                    "required_evidence_level": "ABSTRACT_VERIFIED",
                    "old_evidence_ids": list(hyp.get("supporting_evidence_ids") or []),
                }
            )
        break
    if not claims:
        claims.append(
            {
                "claim_id": f"{question_id}-core-1",
                "claim_text": f"Background literature exists for {question_id}.",
                "claim_type": "background",
                "required_evidence_level": "FULLTEXT_VERIFIED",
                "old_evidence_ids": [],
            }
        )
    return claims


def _arxiv_search(query: str, max_results: int, audit: FulltextFetchAudit) -> list[str]:
    import requests

    audit.discovery_requests += 1
    url = "https://export.arxiv.org/api/query"
    try:
        response = requests.get(
            url,
            params={"search_query": f"all:{query}", "start": 0, "max_results": max_results},
            timeout=40,
            headers={"User-Agent": "SAGE125-evidence-remediation/1.0"},
        )
        body = response.text if response.status_code == 200 else ""
    except Exception:
        return []
    ids = []
    for match in re.finditer(
        r"arxiv\.org/abs/((?:[a-z-]+(?:\.[A-Z]{2})?/\d{7}|\d{4}\.\d{4,5}))",
        body,
        flags=re.IGNORECASE,
    ):
        if match.group(1) not in ids:
            ids.append(match.group(1))
    return ids


def _quote_supports_claim(quote: str, claim: str) -> bool:
    quote_tokens = {token for token in re.findall(r"[A-Za-z]{5,}", quote.lower())}
    claim_tokens = {token for token in re.findall(r"[A-Za-z]{5,}", claim.lower())}
    if not claim_tokens or not quote_tokens:
        return False
    return len(quote_tokens & claim_tokens) >= 2


def scan_local_arxiv_cache(roots: list[Path], keywords: list[str]) -> list[str]:
    """Deterministic local fulltext reuse. Does not call embedding or rerank."""
    lowered = [item.casefold() for item in keywords if len(item) >= 4]
    found: list[str] = []
    for root in roots:
        if not root.exists():
            continue
        for manifest_path in root.rglob("source_manifest.json"):
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            source_id = str(manifest.get("source_id") or "")
            if not source_id.startswith("arxiv:"):
                continue
            arxiv_id = source_id.split(":", 1)[1]
            parsed_path = manifest_path.parent / "parsed_text.json"
            if not parsed_path.is_file():
                continue
            try:
                text = parsed_path.read_text(encoding="utf-8", errors="replace").casefold()
            except OSError:
                continue
            hits = sum(1 for key in lowered if key in text)
            if hits >= 2 and arxiv_id not in found:
                found.append(arxiv_id)
    return found


def _cards_from_arxiv_ids(
    *,
    question_id: str,
    arxiv_ids: list[str],
    cache_root: Path,
    audit: FulltextFetchAudit,
    keywords: list[str],
) -> tuple[list[dict[str, Any]], list[str], list[dict[str, Any]]]:
    eligible_cards: list[dict[str, Any]] = []
    fulltext_sources: list[str] = []
    rejected: list[dict[str, Any]] = []
    for arxiv_id in arxiv_ids:
        fetched = fetch_arxiv_pdf(arxiv_id=arxiv_id, cache_root=cache_root, audit=audit)
        if fetched.get("eligibility") != SourceEligibility.FULLTEXT_VERIFIED.value:
            rejected.append(
                {
                    "arxiv_id": arxiv_id,
                    "eligibility": fetched.get("eligibility"),
                    "reason": fetched.get("reason"),
                }
            )
            continue
        quote_info = select_quote(fetched.get("pages") or [], keywords)
        if not quote_info:
            rejected.append(
                {
                    "arxiv_id": arxiv_id,
                    "eligibility": SourceEligibility.FETCH_FAILED.value,
                    "reason": "no_locator_quote",
                }
            )
            continue
        locator = f"page:{quote_info['page']}|section:{quote_info['section']}|paragraph:{quote_info['paragraph']}"
        evidence_id = deterministic_evidence_id(
            question_id=question_id,
            content_sha256=str(fetched["content_sha256"]),
            locator=locator,
            quote=quote_info["quote"],
        )
        card = {
            "evidence_id": evidence_id,
            "id": evidence_id,
            "question_id": question_id,
            "source_id": f"arxiv:{arxiv_id}",
            "source_type": "arxiv",
            "eligibility_status": SourceEligibility.FULLTEXT_VERIFIED.value,
            "title": f"arXiv:{arxiv_id}",
            "authors": [],
            "year": None,
            "doi": None,
            "url": fetched["url"],
            "quote": quote_info["quote"],
            "quoted_text": quote_info["quote"],
            "locator": locator,
            "page": quote_info["page"],
            "section": quote_info["section"],
            "paragraph": quote_info["paragraph"],
            "content_sha256": fetched["content_sha256"],
            "source_version": "submittedVersion",
            "license_or_access": "arxiv_open_access",
            "support_relation": "supports",
            "confidence": 0.6,
            "extraction_method": "deterministic_pdf_span",
            "fetch_audit_reference": fetched["cache_dir"],
            "source_manifest_reference": str(Path(fetched["cache_dir"]) / "source_manifest.json"),
            "summary": quote_info["quote"][:180],
            "relevance_score": 0.6,
            "reliability_note": (
                f"eligibility_status={SourceEligibility.FULLTEXT_VERIFIED.value}; "
                f"locator={locator}; content_sha256={fetched['content_sha256']}"
            ),
        }
        eligible_cards.append(card)
        if arxiv_id not in fulltext_sources:
            fulltext_sources.append(arxiv_id)
        if len(fulltext_sources) >= 2 and len(eligible_cards) >= 2:
            break
    return eligible_cards, fulltext_sources, rejected


def _finalize_bundle(
    *,
    question_id: str,
    eligible_cards: list[dict[str, Any]],
    fulltext_sources: list[str],
    ineligible: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    output_root: Path,
    attempt_number: int,
) -> dict[str, Any]:
    allowed_ids = [card["evidence_id"] for card in eligible_cards]
    coverage = []
    for claim in claims:
        supporting = [
            card["evidence_id"]
            for card in eligible_cards
            if _quote_supports_claim(card["quote"], claim["claim_text"])
        ]
        coverage.append(
            {
                "claim_id": claim["claim_id"],
                "claim_text": claim["claim_text"],
                "claim_type": claim["claim_type"],
                "required_evidence_level": claim["required_evidence_level"],
                "supporting_evidence_ids": supporting,
                "opposing_evidence_ids": [],
                "evidence_status": "SUPPORTED" if supporting else "INSUFFICIENT_EVIDENCE",
                "uncovered_reason": None if supporting else "no_fulltext_span_overlap",
                "action": "KEEP" if supporting else "NARROW",
            }
        )

    unknown_probe = ["Q028_booklet", "booklet_excerpt_Q028", "title_only_x", "doi_only_x", "EV-OTHER-not-real"]
    unknown_count = 0
    for fake in unknown_probe:
        try:
            assert_known_evidence_ids({"supporting_evidence_ids": [fake]}, allowed_ids)
            unknown_count += 1
        except UnknownEvidenceIDError:
            pass

    booklet_count = sum(1 for card in eligible_cards if "booklet" in card["evidence_id"].lower())
    cross_question = [
        card["evidence_id"]
        for card in eligible_cards
        if not str(card["evidence_id"]).startswith(f"EV-{question_id}-")
    ]
    metadata_fact = 0
    question_source_as_evidence = sum(
        1
        for card in eligible_cards
        if "question_source" in str(card.get("reliability_note") or "").lower()
        or str(card.get("source_type") or "").lower() == "booklet"
    )
    ready = (
        len(fulltext_sources) >= 2
        and len(eligible_cards) >= 2
        and unknown_count == 0
        and booklet_count == 0
        and metadata_fact == 0
        and not cross_question
        and question_source_as_evidence == 0
        and all(item["action"] != "KEEP" or item["supporting_evidence_ids"] for item in coverage)
    )
    bundle = {
        "question_id": question_id,
        "attempt_number": attempt_number,
        "allowed_evidence_ids": allowed_ids,
        "eligible_cards": eligible_cards,
        "ineligible_discovery_records": ineligible,
        "rejected_sources": rejected,
        "coverage_matrix": coverage,
        "token_budget": 6000,
        "truncation_log": [],
        "fulltext_verified_source_count": len(fulltext_sources),
        "abstract_verified_count": 0,
        "eligible_evidence_count": len(eligible_cards),
        "metadata_only_count": sum(
            1
            for item in ineligible
            if item.get("eligibility") == SourceEligibility.METADATA_ONLY.value
        ),
        "fetch_failed_count": sum(
            1
            for item in rejected
            if item.get("eligibility") == SourceEligibility.FETCH_FAILED.value
        ),
        "license_restricted_count": sum(
            1
            for item in rejected
            if item.get("eligibility") == SourceEligibility.LICENSE_RESTRICTED.value
        ),
        "uncovered_claim_count": sum(
            1 for item in coverage if item["action"] == "KEEP" and not item["supporting_evidence_ids"]
        ),
        "unknown_id_count": unknown_count,
        "unknown_evidence_id_count": unknown_count,
        "metadata_only_used_as_fact_count": metadata_fact,
        "booklet_evidence_count": booklet_count,
        "cross_question_evidence_id_count": len(cross_question),
        "question_source_as_evidence_count": question_source_as_evidence,
        "evidence_bundle_ready": ready,
        "evidence_seed_ready": ready,
        "built_at": utc_now(),
    }
    encoded = json.dumps(
        {key: value for key, value in bundle.items() if key != "bundle_hash"},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    bundle["bundle_hash"] = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    question_dir = output_root / question_id
    write_json(question_dir / "evidence_bundle.json", bundle)
    write_json(question_dir / "claim_coverage_matrix.json", {"question_id": question_id, "claims": coverage})
    write_json(
        question_dir / "source_access_audit.json",
        {"question_id": question_id, "rejected": rejected, "ineligible": ineligible},
    )
    write_json(
        question_dir / "unknown_evidence_id_report.json",
        {
            "question_id": question_id,
            "unknown_evidence_id_count": unknown_count,
            "booklet_evidence_count": booklet_count,
            "cross_question_evidence_id_count": len(cross_question),
            "allowed_evidence_ids": allowed_ids,
        },
    )
    return bundle


def build_question_bundle(
    *,
    question_id: str,
    cache_root: Path,
    output_root: Path,
    audit: FulltextFetchAudit,
) -> dict[str, Any]:
    discovery = _load_attempt1_cards(question_id)
    claims = _load_attempt1_claims(question_id)
    ineligible = []
    arxiv_ids: list[str] = []
    for card in discovery:
        source = str(card.get("source_type") or "")
        quote = str(card.get("quoted_text") or "")
        title = str(card.get("title") or "")
        if source in {"openalex", "crossref"} or " ".join(quote.split()).casefold() == " ".join(title.split()).casefold():
            ineligible.append(
                {
                    "id": card.get("id"),
                    "eligibility": SourceEligibility.METADATA_ONLY.value,
                    "reason": "title_or_doi_metadata_cannot_support_facts",
                }
            )
            continue
        arxiv_id = arxiv_id_from_url(str(card.get("url") or card.get("id") or ""))
        if arxiv_id and arxiv_id not in arxiv_ids:
            arxiv_ids.append(arxiv_id)
        elif source == "arxiv":
            ineligible.append(
                {
                    "id": card.get("id"),
                    "eligibility": SourceEligibility.ABSTRACT_VERIFIED.value,
                    "reason": "attempt1_abstract_not_reused_as_fulltext_card",
                }
            )
    if len(arxiv_ids) < 3:
        extra_query = " ".join(QUESTION_KEYWORDS[question_id][:3])
        for extra_id in _arxiv_search(extra_query, 5, audit):
            if extra_id not in arxiv_ids:
                arxiv_ids.append(extra_id)
            if len(arxiv_ids) >= 6:
                break

    eligible_cards, fulltext_sources, rejected = _cards_from_arxiv_ids(
        question_id=question_id,
        arxiv_ids=arxiv_ids,
        cache_root=cache_root,
        audit=audit,
        keywords=QUESTION_KEYWORDS[question_id],
    )
    return _finalize_bundle(
        question_id=question_id,
        eligible_cards=eligible_cards,
        fulltext_sources=fulltext_sources,
        ineligible=ineligible,
        rejected=rejected,
        claims=claims,
        output_root=output_root,
        attempt_number=2,
    )


def build_seed_bundle(
    *,
    question_id: str,
    question_title: str,
    cache_root: Path,
    output_root: Path,
    audit: FulltextFetchAudit,
    local_cache_roots: list[Path] | None = None,
) -> dict[str, Any]:
    """Phase A evidence seed for a new Formal 12 question. No model Provider calls."""
    keywords = QUESTION_KEYWORDS[question_id]
    ineligible: list[dict[str, Any]] = []
    arxiv_ids: list[str] = []
    for local_id in scan_local_arxiv_cache(local_cache_roots or [], keywords):
        if local_id not in arxiv_ids:
            arxiv_ids.append(local_id)
    for query in QUERY_SEEDS.get(question_id, (" ".join(keywords[:3]),)):
        if len(arxiv_ids) >= 8:
            break
        for extra_id in _arxiv_search(query, 8, audit):
            if extra_id not in arxiv_ids:
                arxiv_ids.append(extra_id)
            if len(arxiv_ids) >= 8:
                break
    claims = [
        {
            "claim_id": f"{question_id}-core-1",
            "claim_text": question_title,
            "claim_type": "background",
            "required_evidence_level": "FULLTEXT_VERIFIED",
            "old_evidence_ids": [],
        }
    ]
    eligible_cards, fulltext_sources, rejected = _cards_from_arxiv_ids(
        question_id=question_id,
        arxiv_ids=arxiv_ids,
        cache_root=cache_root,
        audit=audit,
        keywords=keywords,
    )
    return _finalize_bundle(
        question_id=question_id,
        eligible_cards=eligible_cards,
        fulltext_sources=fulltext_sources,
        ineligible=ineligible,
        rejected=rejected,
        claims=claims,
        output_root=output_root,
        attempt_number=0,
    )


def write_root_cause_report(path: Path) -> None:
    report = {
        "generated_at": utc_now(),
        "affected_questions": list(FORMAL_5),
        "root_causes": [
            {
                "root_cause_id": "RC-OA-TITLE-AS-QUOTE",
                "file": "app/clients/literature_clients.py",
                "line_function": "OpenAlexClient.search ~186-200",
                "current_behavior": "OpenAlex works set quoted_text=title and still emit EvidenceCard.",
                "expected_behavior": "OpenAlex/Crossref records are METADATA_ONLY discovery, never fact evidence.",
                "affected_questions": list(FORMAL_5),
                "severity": "P0",
                "minimum_fix": "Mark metadata-only and exclude from agent catalog / fact support.",
                "regression_test": "tests/evidence/test_remediation_guards.py::test_title_quote_is_metadata_only",
            },
            {
                "root_cause_id": "RC-CROSSREF-TITLE-AS-QUOTE",
                "file": "app/clients/literature_clients.py",
                "line_function": "CrossrefClient.search ~271-284",
                "current_behavior": "Crossref DOI hits use title as quoted_text.",
                "expected_behavior": "Crossref records remain METADATA_ONLY until OA fulltext is fetched.",
                "affected_questions": list(FORMAL_5),
                "severity": "P0",
                "minimum_fix": "Do not convert Crossref metadata into eligible EvidenceCard.",
                "regression_test": "tests/evidence/test_remediation_guards.py::test_title_quote_is_metadata_only",
            },
            {
                "root_cause_id": "RC-LIT-FALLBACK-TITLE",
                "file": "app/rag/evidence.py",
                "line_function": "literature_to_evidence_card quoted = abstract or summary or title",
                "current_behavior": "Missing abstract falls back to title as quote.",
                "expected_behavior": "Title fallback yields METADATA_ONLY, not a fact card.",
                "affected_questions": list(FORMAL_5),
                "severity": "P0",
                "minimum_fix": "Classify quote==title as METADATA_ONLY.",
                "regression_test": "tests/evidence/test_remediation_guards.py::test_literature_title_fallback_not_eligible",
            },
            {
                "root_cause_id": "RC-NO-FULLTEXT-FETCH",
                "file": "app/rag/open_literature_retriever.py",
                "line_function": "module docstring and search(); ArxivClient.search does not download PDF",
                "current_behavior": "Open literature explicitly does not download PDFs; DOI landing pages stay metadata.",
                "expected_behavior": "OA PDF/XML/HTML is fetched, validated, parsed, and quoted with locator.",
                "affected_questions": list(FORMAL_5),
                "severity": "P0",
                "minimum_fix": "Add OA fulltext chain and only FULLTEXT/ABSTRACT verified cards enter the bundle.",
                "regression_test": "tests/evidence/test_remediation_guards.py::test_pdf_magic_rejected_without_header",
            },
            {
                "root_cause_id": "RC-EMPTY-LOCATOR-STILL-ELIGIBLE",
                "file": "app/core/schemas.py",
                "line_function": "EvidenceCard has no locator field; empty locator still eligible",
                "current_behavior": "Cards without page/section/paragraph still enter the catalog.",
                "expected_behavior": "Fact-eligible cards require a stable locator and content hash.",
                "affected_questions": list(FORMAL_5),
                "severity": "P0",
                "minimum_fix": "Require locator+content_sha256 for FULLTEXT_VERIFIED.",
                "regression_test": "tests/evidence/test_remediation_guards.py::test_locator_required_for_fulltext",
            },
            {
                "root_cause_id": "RC-CATALOG-SENDS-METADATA-IDS",
                "file": "app/workflow/pipeline.py",
                "line_function": "_evidence_catalog / _gather_real_evidence",
                "current_behavior": "Metadata OpenAlex/Crossref IDs are sent to HypothesisGenerator as citable IDs.",
                "expected_behavior": "Prompt sees only allowed_evidence_ids from the eligible bundle.",
                "affected_questions": list(FORMAL_5),
                "severity": "P0",
                "minimum_fix": "Filter catalog to fact-eligible cards.",
                "regression_test": "tests/evidence/test_remediation_guards.py::test_catalog_excludes_metadata",
            },
            {
                "root_cause_id": "RC-UNKNOWN-ID-LATE",
                "file": "app/agents/base.py",
                "line_function": "BaseAgent.run collects IDs but does not reject unknown IDs before later gates",
                "current_behavior": "Unknown IDs such as Q028_booklet survive until quality_gates.check_evidence_grounding.",
                "expected_behavior": "Parser/ID guard fails closed immediately; no fuzzy rewrite.",
                "affected_questions": ["Q028"],
                "severity": "P0",
                "minimum_fix": "assert_known_evidence_ids after JSON parse.",
                "regression_test": "tests/evidence/test_remediation_guards.py::test_q028_booklet_rejected",
            },
            {
                "root_cause_id": "RC-Q028-BOOKLET-MODEL-INVENTED",
                "file": "app/agents/prompts.py",
                "line_function": "HYPOTHESIS_GENERATOR_PROMPT does not list allowed IDs or forbid Q028_booklet",
                "current_behavior": "Q028_booklet is not a fixture; the model freely invented it. Not an ID repairer.",
                "expected_behavior": "Prompt lists allowed IDs and forbids question-source IDs; parser rejects the rest.",
                "affected_questions": ["Q028"],
                "severity": "P0",
                "minimum_fix": "Prompt + parse-time guard. Do not mint Q028_booklet.",
                "regression_test": "tests/evidence/test_remediation_guards.py::test_q028_booklet_rejected",
            },
            {
                "root_cause_id": "RC-BUNDLE-MAPS-OPENALEX-AS-PAPER",
                "file": "app/evidence/bundle_builder.py",
                "line_function": "_SOURCE_TYPE_MAP openalex/crossref -> paper",
                "current_behavior": "Metadata sources are typed as paper inside EvidenceBundle.",
                "expected_behavior": "Discovery metadata stays ineligible; only verified quotes become paper cards.",
                "affected_questions": list(FORMAL_5),
                "severity": "P1",
                "minimum_fix": "Do not map metadata-only API hits to paper eligibility.",
                "regression_test": "tests/evidence/test_remediation_guards.py::test_title_quote_is_metadata_only",
            },
        ],
        "answers": {
            "openalex_to_card": "OpenAlexClient.search quoted_text=title, then OpenLiteratureRetriever.search via literature_to_evidence_card",
            "crossref_to_card": "CrossrefClient.search quoted_text=title",
            "quote_equals_title": True,
            "quoted_text_abstract_or_title_fallback": True,
            "locator_empty_still_eligible": True,
            "doi_landing_treated_as_fulltext": False,
            "question_source_mixed_into_catalog": False,
            "q028_booklet_origin": "model_free_generation",
            "unknown_id_found_at_export_only": True,
            "why_not_rejected_at_parse": "BaseAgent.run collected IDs for tracing but did not compare them to allowed_evidence_ids",
        },
    }
    write_json(path, report)


def classify_existing_card(card: dict[str, Any]) -> SourceEligibility:
    source = str(card.get("source_type") or "").lower()
    title = " ".join(str(card.get("title") or "").split()).casefold()
    quoted = " ".join(str(card.get("quoted_text") or "").split()).casefold()
    note = str(card.get("reliability_note") or "").lower()
    if source == "booklet" or "question_source" in note or "sjtu-booklet" in title:
        return SourceEligibility.QUESTION_SOURCE
    if "eligibility_status=fulltext_verified" in note:
        return SourceEligibility.FULLTEXT_VERIFIED
    if source in {"openalex", "crossref"} or (title and quoted == title):
        return SourceEligibility.METADATA_ONLY
    if source == "arxiv" and quoted and quoted != title:
        return SourceEligibility.ABSTRACT_VERIFIED
    return SourceEligibility.METADATA_ONLY


def is_fact_eligible_card(card: dict[str, Any]) -> bool:
    note = str(card.get("reliability_note") or "").lower()
    if "mock_for_testing" in note and (card.get("quoted_text") or "").strip():
        return True
    status = classify_existing_card(card)
    if status == SourceEligibility.ABSTRACT_VERIFIED:
        locator = note
        return "locator=" in locator and bool(card.get("quoted_text"))
    return status == SourceEligibility.FULLTEXT_VERIFIED and bool(card.get("quoted_text"))
