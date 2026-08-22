"""Question–document topic relevance: independent of fulltext availability.

Stage A only. No model Provider, embedding, or rerank calls.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from app.formal125.hashes import sha256_canonical_json

POLICY_VERSION = "formal125.question_evidence_relevance.v1"
EVIDENCE_POLICY_VERSION = "formal125.evidence.v3"
GENERIC_BANNED = {"model", "data", "system", "network", "science", "ai"}
Q069_NEGATIVE_ARXIV = ("2411.00681", "2307.15471")

TOPIC_DIRECT = "DIRECT_QUESTION_CORE"
TOPIC_SUPPORT = "SUPPORTING_MECHANISM"
TOPIC_METHOD = "METHOD_RELEVANT"
TOPIC_CONTEXT = "CONTEXT_ONLY"
TOPIC_OFF = "OFF_TOPIC"
TOPIC_UNVERIFIED = "UNVERIFIED_RELEVANCE"

ELIGIBLE_TOPICS = {TOPIC_DIRECT, TOPIC_SUPPORT}

# Anchors come only from the official title/body or named objects in that text.
# Synonyms are recorded with source+reason. Wide tokens are not used alone.
SPEC_TEMPLATES: dict[str, dict[str, Any]] = {
    "Q069": {
        "domain_id": "physics",
        "research_object_anchors": [
            ["diffraction limit"],
            ["optical microscopy", "optical microscope"],
            ["optical resolution", "microscope resolution"],
        ],
        "phenomenon_or_relation_anchors": [
            ["diffraction"],
            ["resolution limit", "resolving power"],
        ],
        "mechanism_or_constraint_anchors": [
            ["Abbe", "Abbe limit", "Abbe diffraction"],
            ["super-resolution", "superresolution", "STED", "PALM", "STORM", "SMLM"],
            ["Rayleigh criterion"],
        ],
        "method_anchors": [["fluorescence microscopy"], ["stimulated emission depletion"]],
        "required_anchor_groups": ["research_object", "phenomenon_or_mechanism"],
        "optional_synonyms": [
            {
                "term": "Abbe",
                "source": "official_question_plus_domain_map",
                "reason": "Standard name of the optical diffraction-limit constraint stated in the official Physics question.",
            },
            {
                "term": "STED",
                "source": "official_question_text",
                "reason": "The official body cites 2014 Nobel techniques that bypass the diffraction limit; STED is one named method of that prize.",
            },
            {
                "term": "PALM",
                "source": "official_question_text",
                "reason": "Same 2014 Nobel bypass-technique family named by the official question body.",
            },
        ],
        "prohibited_unrelated_topics": [
            "network operations",
            "network ai",
            "somatic mutation",
            "mutation burden",
            "ageing phenotypes",
            "geodynamo",
            "geomagnetic",
        ],
        "query_variants": [
            'ti:"diffraction limit" AND (all:microscopy OR all:optics)',
            'all:"super-resolution microscopy" AND all:"diffraction limit"',
            'all:"Abbe diffraction" AND all:microscopy',
        ],
        "evidence_roles": ["direct_core", "supporting_mechanism"],
    },
    "Q003": {
        "domain_id": "chemistry",
        "research_object_anchors": [
            ["pigment", "pigments"],
            ["YInMn", "YInMn Blue"],
            ["chromophore"],
        ],
        "phenomenon_or_relation_anchors": [["color", "colour"], ["synthetic pigment"]],
        "mechanism_or_constraint_anchors": [["inorganic pigment"], ["structural color", "structural colour"]],
        "method_anchors": [["spectroscopy"], ["crystal structure"]],
        "required_anchor_groups": ["research_object", "phenomenon_or_mechanism"],
        "optional_synonyms": [
            {
                "term": "YInMn Blue",
                "source": "official_question_text",
                "reason": "Named explicitly in the official Chemistry question.",
            }
        ],
        "prohibited_unrelated_topics": ["diffraction limit", "geodynamo", "pandemic", "mars manufacturing"],
        "query_variants": [
            "ti:pigment",
            "all:pigment AND all:chromophore",
            'all:"synthetic pigment"',
            "all:pigment AND all:inorganic",
        ],
        "evidence_roles": ["direct_core", "supporting_mechanism"],
    },
    "Q026": {
        "domain_id": "biology",
        "research_object_anchors": [["stem cell", "stem cells"], ["pluripotent"], ["cell differentiation"]],
        "phenomenon_or_relation_anchors": [["reprogramming"], ["lineage restriction"], ["differentiate"]],
        "mechanism_or_constraint_anchors": [["Yamanaka"], ["iPSC", "induced pluripotent"]],
        "method_anchors": [["cell culture"], ["transcription factor"]],
        "required_anchor_groups": ["research_object", "phenomenon_or_mechanism"],
        "optional_synonyms": [
            {
                "term": "iPSC",
                "source": "official_question_text",
                "reason": "Official body discusses reprogrammed cells versus embryonic stem cells.",
            }
        ],
        "prohibited_unrelated_topics": ["diffraction limit", "mars manufacturing", "photovoltaic"],
        "query_variants": [
            'all:"cell reprogramming" AND all:pluripotent',
            'all:"stem cell" AND all:differentiation',
            'ti:"induced pluripotent"',
        ],
        "evidence_roles": ["direct_core", "supporting_mechanism"],
    },
    "Q013": {
        "domain_id": "medicine_and_health",
        "research_object_anchors": [["pandemic"], ["epidemic"], ["outbreak"]],
        "phenomenon_or_relation_anchors": [["forecast", "forecasting"], ["predict", "prediction"]],
        "mechanism_or_constraint_anchors": [["influenza"], ["infectious disease"]],
        "method_anchors": [["compartmental model"], ["nowcasting"]],
        "required_anchor_groups": ["research_object", "phenomenon_or_mechanism"],
        "optional_synonyms": [
            {
                "term": "outbreak",
                "source": "official_question",
                "reason": "Same research object as pandemic/epidemic prediction in the official title.",
            }
        ],
        "prohibited_unrelated_topics": ["diffraction limit", "geodynamo", "YInMn"],
        "query_variants": [
            'ti:pandemic AND (all:forecast OR all:predict)',
            'all:"epidemic forecast" AND all:influenza',
            'all:"infectious disease" AND all:outbreak AND all:prediction',
        ],
        "evidence_roles": ["direct_core", "supporting_mechanism"],
    },
    "Q109": {
        "domain_id": "ecology",
        "research_object_anchors": [
            ["Earth magnetic field", "earth's magnetic field", "geomagnetic field"],
            ["geodynamo"],
            ["outer core"],
        ],
        "phenomenon_or_relation_anchors": [["geomagnetic"], ["magnetic field"]],
        "mechanism_or_constraint_anchors": [["dynamo"], ["liquid-metal", "liquid metal"], ["ionosphere"]],
        "method_anchors": [["magnetohydrodynamic"], ["paleomagnetic"]],
        "required_anchor_groups": ["research_object", "phenomenon_or_mechanism"],
        "optional_synonyms": [
            {
                "term": "geodynamo",
                "source": "official_question_text",
                "reason": "Official body states the liquid-metal outer core creates electric currents that form the magnetic field.",
            }
        ],
        "prohibited_unrelated_topics": ["diffraction limit", "somatic mutation", "network operations", "pigment"],
        "query_variants": [
            'ti:geodynamo OR ti:"geomagnetic dynamo"',
            'all:"Earth magnetic field" AND all:"outer core"',
            'all:geomagnetic AND all:dynamo AND all:core',
        ],
        "evidence_roles": ["direct_core", "supporting_mechanism"],
    },
    "Q091": {
        "domain_id": "information_science",
        "research_object_anchors": [["processing speed"], ["computing power"], ["Moore's law", "Moores law", "Moore law"]],
        "phenomenon_or_relation_anchors": [["transistor"], ["physical limit", "fundamental limit"]],
        "mechanism_or_constraint_anchors": [["Landauer"], ["quantum computer", "quantum computing"]],
        "method_anchors": [["silicon chip"], ["miniaturization"]],
        "required_anchor_groups": ["research_object", "phenomenon_or_mechanism"],
        "optional_synonyms": [
            {
                "term": "Landauer",
                "source": "official_question_text",
                "reason": "Official body says laws of physics prevent further expansion of computing power.",
            }
        ],
        "prohibited_unrelated_topics": ["diffraction limit", "geodynamo", "pandemic", "mars manufacturing"],
        "query_variants": [
            'all:"Moore" AND all:transistor AND all:limit',
            'all:Landauer AND all:computation',
            'ti:"fundamental limits" AND all:computing',
        ],
        "evidence_roles": ["direct_core", "supporting_mechanism"],
    },
    "Q089": {
        "domain_id": "engineering_and_materials_science",
        "research_object_anchors": [
            ["energy-conversion", "energy conversion"],
            ["photovoltaic"],
            ["conversion efficiency"],
        ],
        "phenomenon_or_relation_anchors": [["efficiency limit"], ["Shockley", "Shockley-Queisser"]],
        "mechanism_or_constraint_anchors": [["recombination"], ["thermoelectric"], ["thermophotovoltaic"]],
        "method_anchors": [["solar cell"], ["bandgap"]],
        "required_anchor_groups": ["research_object", "phenomenon_or_mechanism"],
        "optional_synonyms": [
            {
                "term": "Shockley-Queisser",
                "source": "official_question_text",
                "reason": "Official body discusses the current limit on photovoltaic conversion efficiency.",
            }
        ],
        "prohibited_unrelated_topics": ["diffraction limit", "geodynamo", "consciousness", "mars manufacturing"],
        "query_variants": [
            'all:"Shockley-Queisser" OR all:"Shockley Queisser"',
            'all:"photovoltaic efficiency" AND all:limit',
            'all:"energy conversion efficiency" AND all:thermoelectric',
        ],
        "evidence_roles": ["direct_core", "supporting_mechanism"],
    },
    "Q046": {
        "domain_id": "astronomy",
        "research_object_anchors": [["extra dimensions"], ["spacetime"], ["compactification"]],
        "phenomenon_or_relation_anchors": [["Kaluza", "Kaluza-Klein"], ["string theor"]],
        "mechanism_or_constraint_anchors": [["hidden dimensions"], ["compact extra"]],
        "method_anchors": [["collider"], ["gravitational"]],
        "required_anchor_groups": ["research_object", "phenomenon_or_mechanism"],
        "optional_synonyms": [
            {
                "term": "Kaluza-Klein",
                "source": "official_question_text",
                "reason": "Official body discusses extra spatial dimensions suggested by string theory.",
            }
        ],
        "prohibited_unrelated_topics": ["diffraction limit", "pandemic", "pigment", "mars manufacturing"],
        "query_variants": [
            'all:"extra dimensions" AND (all:spacetime OR all:compactification)',
            'all:"Kaluza-Klein" AND all:dimension',
            'ti:"extra dimensions" AND all:string',
        ],
        "evidence_roles": ["direct_core", "supporting_mechanism"],
    },
    "Q095": {
        "domain_id": "neuroscience",
        "research_object_anchors": [["consciousness"], ["neural correlates"]],
        "phenomenon_or_relation_anchors": [["subjective experience"], ["awareness"]],
        "mechanism_or_constraint_anchors": [["NCC"], ["integrated information"], ["global workspace"]],
        "method_anchors": [["fMRI"], ["EEG"]],
        "required_anchor_groups": ["research_object", "phenomenon_or_mechanism"],
        "optional_synonyms": [
            {
                "term": "neural correlates",
                "source": "official_question_text",
                "reason": "Official body locates the disagreement on mechanisms and location of consciousness.",
            }
        ],
        "prohibited_unrelated_topics": ["diffraction limit", "geodynamo", "photovoltaic", "mars manufacturing"],
        "query_variants": [
            'all:"neural correlates of consciousness"',
            'ti:consciousness AND all:neuroscience',
            'all:consciousness AND all:"global workspace"',
        ],
        "evidence_roles": ["direct_core", "supporting_mechanism"],
    },
    "Q088": {
        "domain_id": "engineering_and_materials_science",
        "research_object_anchors": [["Mars manufacturing"], ["in-situ resource", "ISRU"], ["regolith"]],
        "phenomenon_or_relation_anchors": [["additive manufacturing"], ["in situ"]],
        "mechanism_or_constraint_anchors": [["Martian"], ["space manufacturing"]],
        "method_anchors": [["3D print", "3-D print"], ["sinter"]],
        "required_anchor_groups": ["research_object", "phenomenon_or_mechanism"],
        "optional_synonyms": [
            {
                "term": "ISRU",
                "source": "official_question_text",
                "reason": "Official body says Mars manufacturing must use resources the planet has to offer.",
            }
        ],
        "prohibited_unrelated_topics": ["diffraction limit", "geodynamo", "consciousness", "pandemic"],
        "query_variants": [
            'all:Mars AND all:ISRU',
            'all:"in-situ resource" AND all:Mars',
            'all:regolith AND all:manufacturing AND all:Mars',
        ],
        "evidence_roles": ["direct_core", "supporting_mechanism"],
    },
}


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").casefold()).strip()


def phrase_in(text: str, phrase: str) -> bool:
    hay = _norm(text)
    needle = _norm(phrase)
    if not needle or not hay:
        return False
    if needle in hay:
        return True
    return needle.replace(" ", "") in hay.replace(" ", "")


def group_hits(text: str, groups: list[list[str]]) -> list[str]:
    hits: list[str] = []
    for group in groups:
        for variant in group:
            if phrase_in(text, variant):
                hits.append(variant)
                break
    return hits


def assessment_cache_key(
    *,
    question_id: str,
    question_hash: str,
    domain_id: str,
    query_spec_hash: str,
    relevance_spec_hash: str,
    evidence_policy_hash: str,
    source_content_sha256: str,
) -> str:
    payload = {
        "question_id": question_id,
        "question_hash": question_hash,
        "domain_id": domain_id,
        "query_spec_hash": query_spec_hash,
        "relevance_spec_hash": relevance_spec_hash,
        "evidence_policy_hash": evidence_policy_hash,
        "source_content_sha256": source_content_sha256,
    }
    return sha256_canonical_json(payload)


class RelevanceAssessmentCache:
    """Question-bound relevance decisions. Content parse cache is separate."""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}

    def get(self, key: str) -> dict[str, Any] | None:
        return self._store.get(key)

    def put(self, key: str, assessment: Mapping[str, Any]) -> None:
        self._store[key] = dict(assessment)

    def get_for_question(self, key: str, question_id: str, question_hash: str) -> dict[str, Any] | None:
        item = self._store.get(key)
        if item is None:
            return None
        if item.get("question_id") != question_id or item.get("question_hash") != question_hash:
            return None
        return item


def build_relevance_spec(catalog_item: Mapping[str, Any]) -> dict[str, Any]:
    question_id = str(catalog_item["question_id"])
    template = SPEC_TEMPLATES[question_id]
    for group_name in (
        "research_object_anchors",
        "phenomenon_or_relation_anchors",
        "mechanism_or_constraint_anchors",
    ):
        for group in template[group_name]:
            for term in group:
                if _norm(term) in GENERIC_BANNED:
                    raise ValueError(f"{question_id} uses banned generic anchor {term}")
    spec = {
        "question_id": question_id,
        "question_hash": catalog_item["question_hash"],
        "domain_id": template["domain_id"],
        "catalog_domain_id": catalog_item.get("domain_id"),
        "original_question": catalog_item.get("original_title"),
        "original_question_text": catalog_item.get("original_question_text") or catalog_item.get("original_title"),
        "research_object_anchors": template["research_object_anchors"],
        "phenomenon_or_relation_anchors": template["phenomenon_or_relation_anchors"],
        "mechanism_or_constraint_anchors": template["mechanism_or_constraint_anchors"],
        "method_anchors": template["method_anchors"],
        "required_anchor_groups": template["required_anchor_groups"],
        "optional_synonyms": template["optional_synonyms"],
        "prohibited_unrelated_topics": template["prohibited_unrelated_topics"],
        "query_variants": template["query_variants"],
        "evidence_roles": template["evidence_roles"],
        "policy_version": POLICY_VERSION,
    }
    spec["spec_hash"] = sha256_canonical_json(spec)
    spec["query_spec_hash"] = sha256_canonical_json({"query_variants": spec["query_variants"]})
    return spec


def assess_candidate(
    *,
    spec: Mapping[str, Any],
    source_id: str,
    source_content_sha256: str,
    title: str,
    abstract: str,
    fulltext: str,
    query_origin: str,
    discovery_rank: int | None,
    discovery_relevance_score: float | None,
    fulltext_available: bool,
    evidence_policy_hash: str,
) -> dict[str, Any]:
    title_n = title or ""
    abstract_n = abstract or ""
    full_n = fulltext or ""
    combined = " ".join([title_n, abstract_n, full_n])
    object_hits = group_hits(combined, spec["research_object_anchors"])
    phenom_hits = group_hits(combined, spec["phenomenon_or_relation_anchors"])
    mech_hits = group_hits(combined, spec["mechanism_or_constraint_anchors"])
    method_hits = group_hits(combined, spec["method_anchors"])
    title_object = group_hits(title_n, spec["research_object_anchors"])
    title_phenom = group_hits(title_n, spec["phenomenon_or_relation_anchors"])
    title_mech = group_hits(title_n, spec["mechanism_or_constraint_anchors"])
    full_object = group_hits(full_n, spec["research_object_anchors"])
    full_phenom = group_hits(full_n, spec["phenomenon_or_relation_anchors"])
    full_mech = group_hits(full_n, spec["mechanism_or_constraint_anchors"])
    negative = [term for term in spec["prohibited_unrelated_topics"] if phrase_in(combined, term)]
    arxiv_id = source_id.split(":")[-1] if source_id else ""
    if spec["question_id"] == "Q069" and arxiv_id in Q069_NEGATIVE_ARXIV:
        negative.append(f"permanent_negative:{arxiv_id}")

    object_ok = bool(object_hits)
    phenom_or_mech = bool(phenom_hits or mech_hits)
    locatable = bool(full_object or full_phenom or full_mech)
    domain_alignment = spec.get("domain_id") == spec.get("catalog_domain_id") or bool(object_ok)

    if spec["question_id"] == "Q069" and arxiv_id in Q069_NEGATIVE_ARXIV:
        status = TOPIC_OFF
    elif not fulltext_available:
        status = TOPIC_UNVERIFIED
    elif negative and not object_ok:
        status = TOPIC_OFF
    elif not object_ok:
        status = TOPIC_OFF if not (phenom_hits or mech_hits or method_hits) else TOPIC_CONTEXT
    elif object_ok and phenom_or_mech and locatable and (title_object or title_phenom or title_mech or full_object):
        status = TOPIC_DIRECT
    elif object_ok and mech_hits and locatable:
        status = TOPIC_SUPPORT
    elif method_hits and not phenom_or_mech:
        status = TOPIC_METHOD
    elif object_ok:
        status = TOPIC_CONTEXT
    else:
        status = TOPIC_OFF

    accepted = (
        status in ELIGIBLE_TOPICS
        and fulltext_available
        and locatable
        and object_ok
        and phenom_or_mech
        and not (spec["question_id"] == "Q069" and arxiv_id in Q069_NEGATIVE_ARXIV)
    )
    role = {
        TOPIC_DIRECT: "direct_core",
        TOPIC_SUPPORT: "supporting_mechanism",
        TOPIC_METHOD: "method_only",
        TOPIC_CONTEXT: "context_only",
        TOPIC_OFF: "rejected",
        TOPIC_UNVERIFIED: "unverified",
    }[status]
    local_score = min(
        1.0,
        0.25 * len(object_hits) + 0.2 * len(phenom_hits) + 0.2 * len(mech_hits) + 0.1 * int(locatable),
    )
    assessment = {
        "question_id": spec["question_id"],
        "question_hash": spec["question_hash"],
        "source_id": source_id,
        "source_content_sha256": source_content_sha256,
        "title": title,
        "abstract_available": bool(abstract),
        "fulltext_available": fulltext_available,
        "title_anchor_matches": title_object + title_phenom + title_mech,
        "abstract_anchor_matches": group_hits(abstract_n, spec["research_object_anchors"]),
        "fulltext_anchor_matches": full_object + full_phenom + full_mech,
        "research_object_coverage": object_hits,
        "phenomenon_relation_coverage": phenom_hits,
        "mechanism_constraint_coverage": mech_hits,
        "method_coverage": method_hits,
        "domain_alignment": bool(domain_alignment),
        "negative_topic_hits": negative,
        "query_origin": query_origin,
        "discovery_rank": discovery_rank,
        "discovery_relevance_score": discovery_relevance_score,
        "local_relevance_score": round(local_score, 4),
        "relevance_status": status,
        "evidence_role": role,
        "acceptance_decision": "ACCEPT" if accepted else "REJECT",
        "acceptance_reason": "object+phenomenon_or_mechanism+locatable_fulltext" if accepted else None,
        "rejection_reason": None
        if accepted
        else (
            "permanent_q069_negative"
            if spec["question_id"] == "Q069" and arxiv_id in Q069_NEGATIVE_ARXIV
            else "missing_object_or_phenomenon_or_locator_or_fulltext_or_negative"
        ),
        "cache_key": assessment_cache_key(
            question_id=spec["question_id"],
            question_hash=spec["question_hash"],
            domain_id=str(spec["domain_id"]),
            query_spec_hash=str(spec["query_spec_hash"]),
            relevance_spec_hash=str(spec["spec_hash"]),
            evidence_policy_hash=evidence_policy_hash,
            source_content_sha256=source_content_sha256,
        ),
    }
    assessment["assessment_hash"] = sha256_canonical_json(assessment)
    return assessment


def evaluate_seed_gate(
    *,
    question_id: str,
    assessments: list[Mapping[str, Any]],
    eligible_ids: list[str],
    rejected_source_ids: list[str],
    spec_hash: str,
    extra_blockers: list[str] | None = None,
) -> dict[str, Any]:
    counts = {
        TOPIC_DIRECT: 0,
        TOPIC_SUPPORT: 0,
        TOPIC_METHOD: 0,
        TOPIC_CONTEXT: 0,
        TOPIC_OFF: 0,
        TOPIC_UNVERIFIED: 0,
    }
    accepted_status: list[str] = []
    for item in assessments:
        status = str(item.get("relevance_status") or TOPIC_UNVERIFIED)
        counts[status] = counts.get(status, 0) + 1
        if item.get("acceptance_decision") == "ACCEPT":
            accepted_status.append(status)
    blockers = list(extra_blockers or [])
    if sum(1 for item in assessments if item.get("acceptance_decision") == "ACCEPT") < 2:
        blockers.append("fewer_than_two_accepted_sources")
    if counts[TOPIC_DIRECT] < 1:
        blockers.append("missing_direct_question_core")
    if not any(status in {TOPIC_DIRECT, TOPIC_SUPPORT} for status in accepted_status[1:2]) and counts[TOPIC_DIRECT] + counts[TOPIC_SUPPORT] < 2:
        blockers.append("second_source_not_direct_or_supporting")
    if any(item.get("acceptance_decision") == "ACCEPT" and item.get("relevance_status") == TOPIC_OFF for item in assessments):
        blockers.append("off_topic_marked_eligible")
    ready = not blockers
    result = {
        "question_id": question_id,
        "source_count": len(assessments),
        "fulltext_verified_count": sum(1 for item in assessments if item.get("fulltext_available")),
        "direct_core_count": counts[TOPIC_DIRECT],
        "supporting_mechanism_count": counts[TOPIC_SUPPORT],
        "method_relevant_count": counts[TOPIC_METHOD],
        "context_only_count": counts[TOPIC_CONTEXT],
        "off_topic_count": counts[TOPIC_OFF],
        "unverified_count": counts[TOPIC_UNVERIFIED],
        "anchor_coverage": {
            "direct_or_supporting_accepted": sum(1 for item in assessments if item.get("acceptance_decision") == "ACCEPT")
        },
        "eligible_evidence_ids": eligible_ids,
        "rejected_source_ids": rejected_source_ids,
        "gate_status": "READY" if ready else "NOT_READY",
        "blocking_reasons": blockers,
        "relevance_spec_hash": spec_hash,
    }
    result["seed_hash"] = sha256_canonical_json(result)
    return result


def is_content_bearing(result: Mapping[str, Any]) -> bool:
    if str(result.get("status") or "").lower() == "blocked":
        return False
    if str(result.get("blocked_reason") or ""):
        return False
    hypotheses = result.get("generated_hypotheses")
    if hypotheses == [] or hypotheses is None:
        title = str(result.get("paper_title") or "")
        if "blocked" in title.casefold():
            return False
        if not hypotheses:
            return False
    return True


def write_spec(path: Path, spec: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
