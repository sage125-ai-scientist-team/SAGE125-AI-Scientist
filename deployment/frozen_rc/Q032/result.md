# Evidence Insufficiency in Cross-Domain Biodiversity Estimation: A Semantic Audit of Non-Biological Literature

## Input Question
How many species are there on Earth?

## Domain
Biology

## Validation Status
needs_data

## Problem Statement
The question seeks a quantitative estimate of global biodiversity (total species count). However, the scientific boundary is constrained by the lack of a universal species definition (~50 definitions) and the vast unknown diversity of microorganisms. The core challenge is that current estimates range widely (5.3 million to 1 trillion), and this uncertainty cannot be resolved or validated using the provided evidence base, which consists of unrelated domains (aerospace engineering, statistical theory, photovoltaics, and digital twin networks).

## Rationale
Scientific rigor requires that factual claims be traceable to relevant evidence. The allowed evidence IDs (EV-Q032-937462cedf356e0b64320f6a, EV-Q032-887ca7099a0410db0437e533, EV-Q032-963939f677d755983d768817, EV-Q032-de1b2c0fb2828bc6ac595d85) do not contain biological taxonomy data, biodiversity models, or species richness estimates. Therefore, the only scientifically valid conclusion derivable from this specific evidence set is that it is insufficient to answer the question. This report formalizes this insufficiency as a verifiable hypothesis through a semantic audit of the provided texts.

## Generated Hypotheses

### Hypothesis 1
- **Hypothesis**: Current estimates of Earth's total species count (5.3 million to 1 trillion) cannot be scientifically validated or refined using the provided evidence base, as no allowed evidence cards contain biological taxonomy, biodiversity sampling data, or species richness models.
- **Mechanism**: Scientific validation requires domain-relevant evidence. The allowed evidence set consists exclusively of aerospace engineering (EV-Q032-937462cedf356e0b64320f6a), statistical theory for unknown rate parameters (EV-Q032-887ca7099a0410db0437e533), photovoltaic physics (EV-Q032-963939f677d755983d768817), and digital twin networks (EV-Q032-de1b2c0fb2828bc6ac595d85). None of these domains provide observational data, taxonomic frameworks, or ecological models necessary to verify species counts. Therefore, any specific numerical claim derived from this evidence set would be epistemically invalid.
- **Falsifiable Prediction**: If a comprehensive audit of the four allowed evidence IDs reveals zero mentions of 'species', 'taxonomy', 'biodiversity', 'OTU', 'ASV', or related biological terms, then the hypothesis that the current evidence base is insufficient for validating species counts is confirmed.
- **Required Observations**: Full-text semantic search of EV-Q032-937462cedf356e0b64320f6a for biological taxonomy terms；Full-text semantic search of EV-Q032-887ca7099a0410db0437e533 for biodiversity or species estimation content；Full-text semantic search of EV-Q032-963939f677d755983d768817 for ecological or taxonomic data；Full-text semantic search of EV-Q032-de1b2c0fb2828bc6ac595d85 for biological network or species-related digital twin applications
- **Risk of Being Wrong**: Low risk. The evidence extraction result already explicitly identifies a knowledge gap and notes topical irrelevance. The only risk is if the quoted text snippets are unrepresentative and the full texts actually contain relevant biological data not captured in the extraction.

### Hypothesis 2
- **Hypothesis**: The wide uncertainty range in Earth's species estimates (5.3 million to 1 trillion) is primarily driven by methodological differences in handling unknown microbial diversity and varying species definitions, rather than by empirical sampling gaps alone; however, this hypothesis cannot be tested with the current allowed evidence IDs.
- **Mechanism**: Species richness estimation depends critically on the operational definition of 'species' (e.g., morphological vs. phylogenetic vs. ecological) and on extrapolation methods for unsampled microbial taxa. Different combinations of these methodological choices produce orders-of-magnitude variation in global estimates. Testing this mechanism requires access to comparative studies that apply multiple species concepts and extrapolation models to the same datasets, which is absent from the allowed evidence.
- **Falsifiable Prediction**: If future evidence were to show that all major species estimation studies use identical species definitions and extrapolation methods yet still produce estimates spanning five orders of magnitude, then methodological heterogeneity would be falsified as the primary driver of uncertainty.
- **Required Observations**: Comparative analysis of species richness estimates using different species concepts applied to identical sample sets；Quantification of variance attributable to species definition choice versus sampling effort；Meta-analysis of microbial diversity extrapolation methods and their sensitivity to parameter assumptions
- **Risk of Being Wrong**: High risk. This hypothesis is grounded in general biodiversity science literature but has zero support from the allowed evidence IDs. It is presented solely as a knowledge_gap-derived candidate direction that cannot currently be validated.

## Technical Details
This experiment is designed to validate the hypothesis that the provided evidence base (EV-Q032-937462cedf356e0b64320f6a, EV-Q032-887ca7099a0410db0437e533, EV-Q032-963939f677d755983d768817, EV-Q032-de1b2c0fb2828bc6ac595d85) is insufficient for estimating Earth's total species count. The methodology involves a systematic semantic audit of the full text of each allowed EvidenceCard. We will define a controlled vocabulary of biological taxonomy and biodiversity terms (e.g., 'species', 'taxonomy', 'biodiversity', 'OTU', 'ASV', 'richness', 'ecology'). The experiment will scan the content of each evidence ID for these terms. The primary metric is the presence/absence of relevant domain-specific terminology. If zero matches are found across all four IDs, the hypothesis that the evidence base is epistemically invalid for this specific biological question is confirmed. This approach treats the evidence sufficiency as a binary classification problem: Relevant vs. Irrelevant.

## Datasets
### Source


```json
[
  "EV-Q032-937462cedf356e0b64320f6a",
  "EV-Q032-887ca7099a0410db0437e533",
  "EV-Q032-963939f677d755983d768817",
  "EV-Q032-de1b2c0fb2828bc6ac595d85"
]
```


### Target
Binary relevance classification (Relevant/Irrelevant) for Earth species count estimation.

## Paper Abstract
Background: Estimating the total number of species on Earth is a fundamental challenge in biology, with estimates ranging from 5.3 million to 1 trillion due to definitional ambiguities and undiscovered microbial diversity. Method: This study evaluates whether a specific set of allowed evidence documents (covering aerospace engineering, statistical theory, photovoltaics, and digital twin networks) can support a valid answer to this biological question. We conduct a systematic semantic audit using a controlled vocabulary of biological taxonomy terms. Validation Plan: We verify the absence of relevant biological data in the provided evidence IDs. Results: Pending execution of the semantic audit. The hypothesis predicts that the evidence base is insufficient, preventing any factual claim about species counts from being traced to these sources.

## Methods
1. **Vocabulary Definition**: Compile a list of high-specificity biological terms (e.g., 'species richness', 'taxonomic classification', 'microbial diversity').
2. **Document Retrieval**: Access full text of EV-Q032-937462cedf356e0b64320f6a, EV-Q032-887ca7099a0410db0437e533, EV-Q032-963939f677d755983d768817, and EV-Q032-de1b2c0fb2828bc6ac595d85.
3. **Semantic Search**: Execute keyword and context-aware search for the defined vocabulary.
4. **Relevance Classification**: Label each document as 'Relevant' or 'Irrelevant' based on the presence of biological data supporting species count estimation.
5. **Conclusion Synthesis**: If all documents are labeled 'Irrelevant', conclude that the evidence base is insufficient.

## Experiments
### Baselines


```json
[
  "Random Keyword Match: Assume a random distribution of scientific terms to estimate false positive rate for biological terms in non-biological texts.",
  "Domain-Specific Baseline: Compare against a known biological abstract (e.g., from PubMed) to ensure the search algorithm correctly identifies positive cases."
]
```


### Metrics


```json
[
  "Term Presence Count: Total number of unique biological terms found across all documents.",
  "Document Relevance Score: Binary indicator (0 or 1) for each document based on term presence.",
  "Overall Evidence Sufficiency Score: Aggregate binary score (0 = Insufficient, 1 = Sufficient)."
]
```


### Ablation
Test the sensitivity of the result by varying the strictness of the keyword list (e.g., narrow list vs. broad list including general statistical terms like 'estimation' which might appear in EV-Q032-887ca7099a0410db0437e533 but lack biological context).

### Validation Protocol
Manual verification of any positive hits to ensure they are not false positives (e.g., the word 'species' appearing in a legal disclaimer or unrelated analogy). Cross-check with the original evidence extraction notes which already flagged these as irrelevant.

## Results
当前状态：待执行验证实验。系统已生成可复现实验脚本、数据字段清单与评价指标，尚未运行真实实验。

## References
- **EV-Q032-937462cedf356e0b64320f6a** · arxiv · arXiv:2404.00800
  - authors: Not available · year: Not available
  - url: https://arxiv.org/pdf/2404.00800.pdf · doi: Not available
  - reliability_note: eligibility_status=FULLTEXT_VERIFIED; topic_relevance_status=DIRECT_QUESTION_CORE; locator=page:3|section:page-3|paragraph:1; content_sha256=03adabf7a0385bfa42709996f708b86a87e8e385497a2b6166ec2f2325a7c812
- **EV-Q032-887ca7099a0410db0437e533** · arxiv · arXiv:2007.02105
  - authors: Not available · year: Not available
  - url: https://arxiv.org/pdf/2007.02105.pdf · doi: Not available
  - reliability_note: eligibility_status=FULLTEXT_VERIFIED; topic_relevance_status=DIRECT_QUESTION_CORE; locator=page:6|section:page-6|paragraph:1; content_sha256=03f8aa647cd75f5ab874d9c89ad9249bdaa8838251f32e35df3f1f877656958c
- **EV-Q032-963939f677d755983d768817** · arxiv · arXiv:1704.06234
  - authors: Not available · year: Not available
  - url: https://arxiv.org/pdf/1704.06234.pdf · doi: Not available
  - reliability_note: eligibility_status=FULLTEXT_VERIFIED; topic_relevance_status=DIRECT_QUESTION_CORE; locator=page:1|section:page-1|paragraph:1; content_sha256=0a5aed16db15c0aac70503e40835f40880c2122015d4b57965d5083b98eb554e
- **EV-Q032-de1b2c0fb2828bc6ac595d85** · arxiv · arXiv:2411.00681
  - authors: Not available · year: Not available
  - url: https://arxiv.org/pdf/2411.00681.pdf · doi: Not available
  - reliability_note: eligibility_status=FULLTEXT_VERIFIED; topic_relevance_status=DIRECT_QUESTION_CORE; locator=page:1|section:page-1|paragraph:1; content_sha256=112dcd15a3619701101d986858cbf66ca68a90f8e21c534f6555e8178793e3ea

## Reviewer Comments
- The candidate hypothesis correctly identifies that the allowed evidence set is topically irrelevant to the biological question of species counts.
- The system appropriately refrains from fabricating an answer or misusing statistical/physics papers (EV-Q032-887ca7099a0410db0437e533, EV-Q032-963939f677d755983d768817) to answer a biodiversity question.
- The proposed experiment is a valid meta-research verification step (semantic audit) to formally confirm the knowledge gap, rather than a futile attempt to derive biological facts from aerospace engineering texts.
- Results field correctly states 'pending' and does not hallucinate experimental outcomes.
- All cited evidence IDs exist in the provided catalog and are used solely to demonstrate their irrelevance.

## Revision History

## Reproducibility Checklist
- List of biological keywords used for search is documented.
- Full text of all four Evidence IDs is accessible and version-controlled.
- Search algorithm code (regex or embedding-based) is saved.
- Criteria for 'meaningful context' exclusion are defined.

