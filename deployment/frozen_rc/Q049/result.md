# Evidence Gap Analysis: Insufficiency of Provided Literature for Explaining Planetary Orbital Stability and Decay

## Input Question
Why don’t the orbits of planets decay and cause them to crash into each other?

## Domain
Astronomy

## Validation Status
needs_data

## Problem Statement
The user inquiry seeks a mechanistic explanation for the stability of planetary orbits against decay and collision, referencing a booklet excerpt that claims orbits decay gradually leading to eventual collapse into the sun. The core scientific challenge is to validate or refute this claim and explain orbital stability using only the provided evidence catalog.

## Rationale
A rigorous analysis of the allowed EvidenceCards (EV-Q049-8bbe55a84dc7ec7a0a7655b0, EV-Q049-62174834a29a81c036ba3f3f, EV-Q049-c36de67711a6d7af2674a742, EV-Q049-d8b0aafaf37dc75c63b51ce4) reveals a complete topical mismatch with celestial mechanics. The cards cover Mars mission logistics, ferroelectric materials, particle physics flavor symmetries, and geodynamo theory, respectively. Consequently, no established facts regarding gravitational dynamics, angular momentum conservation, or tidal dissipation can be extracted. The research plan therefore focuses on verifying this evidence gap rather than proposing ungrounded physical mechanisms.

## Generated Hypotheses

### Hypothesis 1
- **Hypothesis**: Current evidence catalog is insufficient to explain planetary orbital stability or decay; no provided EvidenceCard addresses celestial mechanics, gravitational dynamics, or orbital friction, rendering the question unanswerable within the allowed scope.
- **Mechanism**: The provided evidence set (EV-Q049-8bbe55a84dc7ec7a0a7655b0, EV-Q049-62174834a29a81c036ba3f3f, EV-Q049-c36de67711a6d7af2674a742, EV-Q049-d8b0aafaf37dc75c63b51ce4) covers Mars propellant logistics, ferroelectric materials, particle physics flavor symmetries, and geodynamo theory respectively. None contain information on N-body gravitational interactions, vacuum drag coefficients, or general relativistic orbital corrections necessary to validate or refute claims about planetary orbit decay.
- **Falsifiable Prediction**: If a relevant EvidenceCard containing celestial mechanics data were added to the allowed list, this hypothesis would be falsified; conversely, as long as the allowed_evidence_ids remain restricted to the current four unrelated IDs, the knowledge gap persists and no grounded answer can be generated.
- **Required Observations**: Verification that none of the allowed_evidence_ids contain keywords or concepts related to orbital mechanics, gravity, or planetary motion；Confirmation that evidence_extraction.knowledge_gaps correctly identifies missing astrophysical context；Audit of evidence_catalog relevance_scores showing topical mismatch despite non-zero scores
- **Risk of Being Wrong**: Low risk within system constraints: this hypothesis accurately reflects the current evidence state. Risk only arises if hidden metadata or implicit links in existing cards actually contain relevant orbital data not captured in quoted_text.

### Hypothesis 2
- **Hypothesis**: The booklet's claim that 'orbits do decay very gradually' and planets will 'swirl into the sun' cannot be verified or refuted using the provided evidence, as no EvidenceCard addresses stellar evolution, tidal dissipation, or long-term orbital dynamics.
- **Mechanism**: Validating the booklet excerpt requires evidence on solar mass loss rates, tidal quality factors, or post-main-sequence stellar expansion—none of which appear in the allowed evidence set. The available cards (propellant costs, ferroelectrics, flavor symmetries, geodynamo) are causally and topologically disconnected from stellar-planetary interaction timescales.
- **Falsifiable Prediction**: If any allowed EvidenceCard were found to contain data on solar wind mass loss, tidal torques, or RGB/AGB phase orbital evolution, this hypothesis would be weakened; currently, with zero matching IDs, the claim remains an unverified external assertion.
- **Required Observations**: Text mining of all allowed EvidenceCards for terms like 'tidal', 'mass loss', 'stellar evolution', 'orbital period change'；Cross-reference of booklet_excerpt claims against evidence_extraction.established_facts (currently empty)；Validation that knowledge_gaps explicitly flag the booklet's decay narrative as ungrounded
- **Risk of Being Wrong**: Moderate risk: future evidence ingestion might retroactively validate the booklet, but under current constraints the hypothesis correctly identifies the verification gap without asserting truth or falsehood of the claim itself.

## Technical Details
This research plan addresses a critical knowledge gap identified in the evidence extraction phase. The recommended hypothesis posits that the current evidence catalog is insufficient to explain planetary orbital stability or decay because no provided EvidenceCard addresses celestial mechanics, gravitational dynamics, or orbital friction. Consequently, this experiment design does not propose a physical simulation of orbital dynamics (which would require external data like JPL DE440 or ISM models not present in the allowed evidence). Instead, it designs a meta-analytical verification protocol to rigorously confirm the absence of relevant astronomical data within the allowed EvidenceCards (EV-Q049-8bbe55a84dc7ec7a0a7655b0, EV-Q049-62174834a29a81c036ba3f3f, EV-Q049-c36de67711a6d7af2674a742, EV-Q049-d8b0aafaf37dc75c63b51ce4). The technical approach involves systematic text mining and topical classification of the provided cards to verify their irrelevance to the domain of orbital mechanics, thereby validating the 'insufficient_evidence' status as a robust scientific conclusion under the system's constraints.

## Datasets
### Source


```json
[
  {
    "name": "Allowed Evidence Cards Catalog",
    "description": "The set of four provided EvidenceCards: EV-Q049-8bbe55a84dc7ec7a0a7655b0 (Mars propellant), EV-Q049-62174834a29a81c036ba3f3f (ferroelectric materials), EV-Q049-c36de67711a6d7af2674a742 (particle physics), and EV-Q049-d8b0aafaf37dc75c63b51ce4 (geodynamo). These are the only permissible data sources for factual grounding.",
    "url": null,
    "license": "Unknown"
  }
]
```


### Target


```json
{
  "name": "Evidence Relevance Audit Report",
  "description": "A structured output confirming the topical mismatch between the provided evidence and the query domain (planetary orbital mechanics).",
  "format": "JSON/Text",
  "schema": {
    "evidence_id": "string",
    "topic_classification": "string",
    "relevance_to_orbital_mechanics": "boolean",
    "key_terms_found": "list[string]"
  }
}
```


## Paper Abstract
Background: The question of why planetary orbits do not rapidly decay and lead to collisions is central to celestial mechanics, typically explained by conservation of angular momentum and the vacuum of space. However, a provided booklet excerpt claims orbits decay gradually, leading to eventual collapse into the sun. Method: We conducted a systematic audit of the allowed EvidenceCards (EV-Q049-8bbe55a84dc7ec7a0a7655b0, EV-Q049-62174834a29a81c036ba3f3f, EV-Q049-c36de67711a6d7af2674a742, EV-Q049-d8b0aafaf37dc75c63b51ce4) to determine if they contain data supporting or refuting this claim. Verification Plan: We employed keyword search and topical classification to assess relevance to orbital mechanics, tidal dissipation, and gravitational dynamics. Results: Pending execution of the meta-analytical audit. Preliminary inspection indicates zero relevance, suggesting the question constitutes a knowledge gap within the provided evidence scope.

## Methods
1. **Systematic Keyword Search**: Scan the quoted_text and metadata of all allowed EvidenceCards for terms related to orbital mechanics (e.g., 'orbit', 'gravity', 'Kepler', 'drag', 'ephemeris', 'semi-major axis'). 
2. **Topical Classification**: Manually or algorithmically classify each EvidenceCard into its actual domain (e.g., Aerospace Logistics, Condensed Matter Physics, High-Energy Physics, Geophysics) to demonstrate the disconnect from Astronomy/Celestial Mechanics. 
3. **Gap Analysis**: Document the specific physical mechanisms required to answer the original question (e.g., N-body dynamics, tidal dissipation) and verify their absence in the evidence set. 
4. **Constraint Verification**: Confirm that no external datasets (JPL DE440, etc.) are referenced or used, adhering strictly to the allowed_evidence_ids constraint.

## Experiments
### Baselines


```json
[
  "Null Hypothesis: At least one provided EvidenceCard contains sufficient information to validate or refute claims about planetary orbital decay.",
  "Random Baseline: A random selection of scientific abstracts from unrelated fields (similar to the provided set) to establish a baseline for topical irrelevance."
]
```


### Metrics


```json
[
  "Keyword Hit Rate: Number of orbital-mechanics-related terms found per EvidenceCard (expected: 0).",
  "Topical Match Score: Semantic similarity score between EvidenceCard content and a standard corpus of celestial mechanics literature (expected: near 0).",
  "Evidence Coverage Percentage: Proportion of required physical mechanisms (drag, GW emission, tidal forces) covered by the evidence set (expected: 0%)."
]
```


### Ablation


```json
[
  "Exclude Metadata: Verify that even with title/metadata expansion, no hidden orbital data exists in the cards.",
  "Broaden Search Terms: Expand keyword list to include indirect references (e.g., 'sun', 'planet') to ensure no contextual clues were missed, while still confirming lack of mechanistic data."
]
```


### Validation Protocol
1. **Manual Review**: Human-in-the-loop verification of each EvidenceCard's content against the query domain. 
2. **Cross-Reference Check**: Ensure that no 'title_only' or 'doi_only' entries are mistakenly treated as full evidence. 
3. **Consistency Check**: Verify that the conclusion of 'insufficient_evidence' aligns with the empty supporting_evidence_ids list in the hypothesis.

## Results
当前状态：待执行验证实验。系统已生成可复现实验脚本、数据字段清单与评价指标，尚未运行真实实验。

## References
- **EV-Q049-8bbe55a84dc7ec7a0a7655b0** · arxiv · arXiv:2404.00800
  - authors: Not available · year: Not available
  - url: https://arxiv.org/pdf/2404.00800.pdf · doi: Not available
  - reliability_note: eligibility_status=FULLTEXT_VERIFIED; topic_relevance_status=DIRECT_QUESTION_CORE; locator=page:3|section:page-3|paragraph:1; content_sha256=03adabf7a0385bfa42709996f708b86a87e8e385497a2b6166ec2f2325a7c812
- **EV-Q049-62174834a29a81c036ba3f3f** · arxiv · arXiv:1903.03884
  - authors: Not available · year: Not available
  - url: https://arxiv.org/pdf/1903.03884.pdf · doi: Not available
  - reliability_note: eligibility_status=FULLTEXT_VERIFIED; topic_relevance_status=DIRECT_QUESTION_CORE; locator=page:2|section:page-2|paragraph:1; content_sha256=0fc49d2917f632d6c8511dfdc2c9217a5da9901f8bddbb60a9c70fa2e592b779
- **EV-Q049-c36de67711a6d7af2674a742** · arxiv · arXiv:hep-ph/9705325
  - authors: Not available · year: Not available
  - url: https://arxiv.org/pdf/hep-ph/9705325.pdf · doi: Not available
  - reliability_note: eligibility_status=FULLTEXT_VERIFIED; topic_relevance_status=DIRECT_QUESTION_CORE; locator=page:5|section:page-5|paragraph:1; content_sha256=136034761e52c5cd5babe265f8efa85d3dfec165bb0626387dc98fe0176fc0b7
- **EV-Q049-d8b0aafaf37dc75c63b51ce4** · arxiv · arXiv:1605.01321
  - authors: Not available · year: Not available
  - url: https://arxiv.org/pdf/1605.01321.pdf · doi: Not available
  - reliability_note: eligibility_status=FULLTEXT_VERIFIED; topic_relevance_status=DIRECT_QUESTION_CORE; locator=page:1|section:page-1|paragraph:1; content_sha256=17d94563ae466610701a8317402bf805b50fa68e732879f0b630377374606d77

## Reviewer Comments
- The revised hypothesis correctly identifies the query as a 'knowledge_gap' due to the complete absence of relevant EvidenceCards for celestial mechanics.
- All references to external datasets (JPL DE440, ISM models) have been successfully removed from the experiment design, resolving the critical issue of external data dependency.
- The experimental design has been appropriately reframed as a meta-analytical audit of the evidence catalog rather than a physical simulation, adhering strictly to allowed evidence constraints.
- Supporting_evidence_ids remains correctly empty, avoiding any force-fitting of irrelevant cards (e.g., geodynamo or propellant costs).
- Results field correctly states 'pending' without fabrication, and the validation protocol is reproducible within the system's current scope.

## Revision History
- auto_revision_1: 依据评审意见重做假设与实验设计。

## Reproducibility Checklist
- List of allowed EvidenceCards (IDs and quoted_text) archived.
- Keyword list for orbital mechanics defined and documented.
- Classification criteria for 'relevant' vs 'irrelevant' evidence explicitly stated.
- Verification that no external data sources were accessed during the audit.
- Final audit report format standardized for JSON output.

