# Quantifying Domain Mismatch: Why Particle Physics and Earth System Literature Cannot Validate Autonomous Vehicle Feasibility

## Input Question
Is a future of only self-driving cars realistic?

## Domain
Engineering & Materials Science

## Validation Status
needs_data

## Problem Statement
The feasibility of a future consisting exclusively of self-driving cars is contingent upon resolving critical technical barriers (sensors, communication, infrastructure, vehicle response) and societal challenges (public perception). However, the currently allowed evidence set comprises literature on particle physics colliders and Earth system detectability, creating a total domain mismatch that prevents direct empirical validation of automotive engineering claims.

## Rationale
Scientific evaluation requires domain-relevant premises. The provided EvidenceCards (EV-Q090-de296c7bfdc43aaac33bc02b, EV-Q090-5c9eb48686fdd187834de03e, EV-Q090-267892bb514b8e3a1a05cc47, EV-Q090-a5701a35b0e252cde040b3ee) address high-energy physics and planetary biosignatures, containing zero semantic overlap with autonomous vehicle (AV) technologies such as LiDAR, V2X communication, or SAE automation levels. Therefore, the primary scientific task is to rigorously quantify this domain mismatch to demonstrate that the question cannot be answered using the allowed evidence, rather than attempting to derive unsupported engineering conclusions.

## Generated Hypotheses

### Hypothesis 1
- **Hypothesis**: Domain Mismatch Insufficiency Hypothesis: The realism of a future with only self-driving cars cannot be scientifically evaluated using the currently allowed evidence set, as the provided sources (EV-Q090-de296c7bfdc43aaac33bc02b, EV-Q090-5c9eb48686fdd187834de03e, EV-Q090-267892bb514b8e3a1a05cc47, EV-Q090-a5701a35b0e252cde040b3ee) exclusively address particle physics and Earth system science, containing zero semantic overlap with autonomous vehicle engineering or societal adoption factors.
- **Mechanism**: Scientific evaluation requires domain-relevant premises. The allowed evidence IDs describe collider strategies, nuclear spin structure, boson decoupling, and planetary biosignatures. These topics share no causal or correlational variables with AV sensors, V2X communication, infrastructure, or public perception. Therefore, any inference about AV feasibility derived solely from these documents is epistemically invalid. This hypothesis treats the 'insufficiency' as a measurable property of the document set relative to a fixed AV taxonomy.
- **Falsifiable Prediction**: If a semantic similarity analysis using a fixed, open-source AV taxonomy reference vector yields a cosine similarity score > 0.2 for any allowed evidence ID, OR if keyword filtering identifies > 0 mentions of core AV terms (LiDAR, V2X, SAE Level, Autonomous Driving), then the hypothesis of total domain mismatch is falsified.
- **Required Observations**: Cosine similarity scores between each allowed evidence ID and a fixed open-source AV taxonomy vector (e.g., SAE J3016 + ISO 26262 terms)；Keyword frequency counts for AV-specific terminology in full text of all four evidence cards；LDA topic modeling output confirming top topics are Physics/Earth Science with < 1% probability mass on Transportation
- **Risk of Being Wrong**: Low. The quoted excerpts explicitly confirm unrelated domains. Risk exists only if full texts contain unindexed sections on AVs, which is statistically negligible given titles/abstracts. Using a fixed open-source taxonomy eliminates reproducibility risk associated with proprietary references.

### Hypothesis 2
- **Hypothesis**: Technical Barrier Dominance Hypothesis (Evidence-Constrained Rejection): While technical barriers (sensors, infrastructure) may theoretically dominate AV feasibility timelines, this specific causal claim is rejected in the current context solely due to lack of supporting data in allowed evidence IDs, not due to scientific invalidity in general engineering literature.
- **Mechanism**: The booklet excerpt posits technical barriers as prerequisites for scaling. However, verifying this dominance requires empirical data on sensor maturity, infrastructure costs, or regulatory milestones. None of the allowed evidence IDs contain such data. Therefore, within the closed system of allowed evidence, this hypothesis has zero support and must be suspended. Its rejection is an artifact of the evidence constraint, not a refutation of the underlying engineering principle.
- **Falsifiable Prediction**: This hypothesis cannot be tested with current allowed evidence. It would only become testable if new evidence IDs containing AV sensor performance metrics or infrastructure deployment data were added to the allowed set. In its current form, it predicts that no such data exists in the current allowed set.
- **Required Observations**: Verification that no allowed evidence ID contains AV technical specifications；Confirmation that booklet excerpt assertions cannot be cross-validated with allowed sources
- **Risk of Being Wrong**: High (as a substantive claim). As a meta-statement about evidence absence, risk is low. It is retained only to satisfy the requirement of showing rejected-but-scientifically-plausible directions, explicitly annotated as evidence-constrained.

## Technical Details
This experiment validates the 'Domain Mismatch Insufficiency Hypothesis' by quantifying the semantic distance between the allowed evidence set (Particle Physics/Earth Science) and the target domain (Autonomous Vehicle Engineering). The core technical approach involves: (1) Constructing a fixed, open-source reference vector for Autonomous Vehicles using standardized taxonomies (SAE J3016, ISO 26262) to ensure reproducibility without proprietary data; (2) Generating dense vector embeddings for the full text of all four allowed Evidence IDs using a pre-trained scientific language model (Qwen-Embedding); (3) Computing cosine similarity scores between each evidence document and the AV reference vector; (4) Performing strict keyword frequency analysis for core AV terms (LiDAR, V2X, SAE Level, Autonomous Driving); and (5) Applying Latent Dirichlet Allocation (LDA) to confirm topic divergence. The hypothesis is falsified if any evidence ID yields a cosine similarity > 0.2 or contains > 0 instances of core AV terminology. The 'Technical Barrier Dominance Hypothesis' is explicitly noted as rejected solely due to the absence of supporting data in the allowed evidence IDs, not due to scientific invalidity in broader engineering contexts.

## Datasets
### Source


```json
[
  {
    "id": "EV-Q090-de296c7bfdc43aaac33bc02b",
    "description": "Full text of arXiv:2511.20417 regarding European Strategy for Particle Physics colliders."
  },
  {
    "id": "EV-Q090-5c9eb48686fdd187834de03e",
    "description": "Full text of arXiv:0910.4753 regarding nuclear spin structure and parity violations."
  },
  {
    "id": "EV-Q090-267892bb514b8e3a1a05cc47",
    "description": "Full text of arXiv:hep-ph/9411291 regarding e+e- linear colliders and boson decoupling."
  },
  {
    "id": "EV-Q090-a5701a35b0e252cde040b3ee",
    "description": "Full text of arXiv:1902.08035 regarding Detectability of Future Earth and biosignatures."
  }
]
```


### Target


```json
{
  "domain": "Autonomous Vehicle Engineering & Societal Impact",
  "reference_taxonomy": "Fixed open-source AV taxonomy derived from SAE J3016 (Levels of Driving Automation) and ISO 26262 (Functional Safety), used solely to generate the semantic reference vector.",
  "required_concepts": [
    "LiDAR/Radar/Camera sensors",
    "V2X Communication protocols",
    "SAE J3016 Automation Levels",
    "Traffic Infrastructure adaptation",
    "Public perception/trust metrics"
  ]
}
```


## Paper Abstract
Background: The question of whether a future of only self-driving cars is realistic depends on resolving technical barriers (sensors, infrastructure) and societal factors (public perception). However, available evidence often suffers from domain irrelevance. Methods: We analyze four allowed evidence cards covering particle physics colliders and Earth system detectability. We construct a fixed reference vector from open-source AV standards (SAE J3016, ISO 26262) and compute cosine similarity scores and keyword frequencies against the evidence texts. Validation Plan: The hypothesis of domain mismatch is tested by verifying that semantic similarity remains below 0.2 and AV-specific keyword counts remain at zero. Results: pending (待执行验证实验). This study demonstrates the necessity of domain-aligned evidence for engineering feasibility assessments.

## Methods
1. Text Ingestion: Parse full PDF/text content of all four allowed Evidence IDs.
2. Reference Vector Construction: Generate a dense embedding vector from a corpus of SAE J3016 and ISO 26262 standard definitions to serve as the fixed AV domain anchor.
3. Keyword Filtering: Apply a strict filter for AV-specific terms (LiDAR, Radar, Camera, V2X, DSRC, C-V2X, SAE Level 3/4/5, Autonomous, Self-driving, Traffic Light Recognition, Pedestrian Detection) across all evidence texts.
4. Semantic Embedding: Generate vector embeddings for each evidence document using Qwen-Embedding.
5. Cosine Similarity Analysis: Compute cosine similarity between each evidence document vector and the fixed AV reference vector.
6. Topic Modeling: Apply Latent Dirichlet Allocation (LDA) to identify top topics in each evidence card and verify none align with transportation engineering.

## Experiments
### Baselines


```json
[
  "Random Baseline: Expected keyword frequency and semantic similarity in a random sample of general scientific literature.",
  "Domain-Mismatch Baseline: Comparison with known unrelated fields (e.g., Marine Biology papers) to establish a floor for semantic similarity scores."
]
```


### Metrics


```json
[
  "Keyword Presence Count: Number of AV-specific terms found in each evidence ID (Hypothesis prediction: 0).",
  "Semantic Similarity Score: Cosine similarity between evidence embeddings and the fixed AV taxonomy reference vector (Hypothesis prediction: < 0.2).",
  "Topic Overlap Index: Jaccard similarity between LDA-derived topics of evidence cards and a standard AV topic list (Hypothesis prediction: 0)."
]
```


### Ablation
Compare results using Abstract-only vs. Full-Text embeddings to ensure no hidden AV-related mentions exist in non-abstract portions of the physics/earth science papers.

### Validation Protocol
Cross-validate keyword search results using two independent NLP libraries (spaCy and NLTK) to rule out parsing errors. Perform manual spot-check of 5% of pages per document to verify automated findings. Ensure the AV reference vector is generated exclusively from open-source standards (SAE/ISO) to guarantee third-party reproducibility.

## Results
当前状态：待执行验证实验。系统已生成可复现实验脚本、数据字段清单与评价指标，尚未运行真实实验。

## References
- **EV-Q090-de296c7bfdc43aaac33bc02b** · arxiv · arXiv:2511.20417
  - authors: Not available · year: Not available
  - url: https://arxiv.org/pdf/2511.20417.pdf · doi: Not available
  - reliability_note: eligibility_status=FULLTEXT_VERIFIED; topic_relevance_status=DIRECT_QUESTION_CORE; locator=page:3|section:page-3|paragraph:1; content_sha256=7ce37b3278fcfff7b1cb1e551eabb708c5e21e6f1ab0282b9dabf9f8bf528758
- **EV-Q090-5c9eb48686fdd187834de03e** · arxiv · arXiv:0910.4753
  - authors: Not available · year: Not available
  - url: https://arxiv.org/pdf/0910.4753.pdf · doi: Not available
  - reliability_note: eligibility_status=FULLTEXT_VERIFIED; topic_relevance_status=DIRECT_QUESTION_CORE; locator=page:2|section:page-2|paragraph:1; content_sha256=9a69ba49d4dfedf130bb5df3b0b9ee2780d7cdd82ffc67d21642e698aff85453
- **EV-Q090-267892bb514b8e3a1a05cc47** · arxiv · arXiv:hep-ph/9411291
  - authors: Not available · year: Not available
  - url: https://arxiv.org/pdf/hep-ph/9411291.pdf · doi: Not available
  - reliability_note: eligibility_status=FULLTEXT_VERIFIED; topic_relevance_status=DIRECT_QUESTION_CORE; locator=page:5|section:page-5|paragraph:1; content_sha256=23af71e76e678acc66db6dbf7a871dde265591ae261f98d9e322b48bbe1e97fe
- **EV-Q090-a5701a35b0e252cde040b3ee** · arxiv · arXiv:1902.08035
  - authors: Not available · year: Not available
  - url: https://arxiv.org/pdf/1902.08035.pdf · doi: Not available
  - reliability_note: eligibility_status=FULLTEXT_VERIFIED; topic_relevance_status=DIRECT_QUESTION_CORE; locator=page:1|section:page-1|paragraph:1; content_sha256=df5243b4eb1392b71a96c7e7a93a4c61cb866a4d16936f6955d9cf6fec15ac5d

## Reviewer Comments
- The revision successfully addresses all required changes from the previous review iteration.
- Hypothesis 1 ('Technical Barrier Dominance Hypothesis') is now explicitly framed as 'Evidence-Constrained Rejection', clarifying that its invalidity in this context is due to lack of allowed evidence IDs rather than scientific unsoundness. This resolves issue required_revision:c6e8fad6918f.
- The reproducibility checklist and experiment technical_details now specify that the semantic reference vector must be derived from fixed, open-source taxonomies (SAE J3016 + ISO 26262), ensuring third-party reproducibility without proprietary data. This resolves issue required_revision:1de82d35324e.
- All supporting_evidence_ids in the recommended hypothesis are valid and present in the provided EvidenceCards.
- Results field remains correctly marked as pending with no fabricated data.
- No causal claims are made regarding AV feasibility; the output strictly adheres to the meta-hypothesis of domain mismatch.

## Revision History
- auto_revision_1: 依据评审意见重做假设与实验设计。

## Reproducibility Checklist
- Provide exact list of AV-specific keywords used for filtering.
- Specify that the 'reference vector' for semantic similarity is generated from a fixed, open-source AV taxonomy (SAE J3016 + ISO 26262) to ensure reproducibility without proprietary textbooks.
- Specify the version of the Qwen-Embedding model used.
- Include raw text extraction logs for each Evidence ID.
- Publish the code for cosine similarity and LDA topic modeling.
- Document the manual spot-check protocol and findings.
- Explicitly state that the 'Technical Barrier Dominance Hypothesis' was rejected solely due to lack of allowed evidence, not scientific invalidity.

