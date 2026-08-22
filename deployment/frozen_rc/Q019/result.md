# Evidence Gap Analysis: Semantic Audit of Allowed Literature for Meridian System Validation

## Input Question
Is there a scientific basis to the Meridian System in traditional Chinese medicine?

## Domain
Medicine & Health

## Validation Status
needs_data

## Problem Statement
The question seeks to determine if the Traditional Chinese Medicine (TCM) concept of the Meridian System—defined as channels for energy flow correlating with organs—has a verifiable scientific basis in terms of anatomical existence or physiological mechanism. The provided booklet excerpt cites NIH suggestions regarding acupuncture's effect on pain processing but does not provide direct evidence for meridians themselves. Crucially, the allowed evidence catalog contains no biomedical literature on TCM, necessitating a rigorous demonstration of this evidence gap.

## Rationale
Scientific validation requires empirical evidence linking the theoretical construct (meridians) to measurable biological phenomena. However, the allowed evidence IDs (EV-Q019-dbd9a094a5d8cb07d59d10c8, EV-Q019-64326f42c48d11f37ce04eef, EV-Q019-6d598a0c1126b6c72f64c56b) are exclusively related to computer science (keyword extraction, LLM surveys) and scientometrics (research drivers). Therefore, no factual claims about meridian mechanisms can be established from these sources. The research plan must formally document this insufficiency through a semantic audit rather than fabricating medical findings.

## Generated Hypotheses

### Hypothesis 1
- **Hypothesis**: Insufficient Evidence Hypothesis: Current allowed evidence catalog contains no data to support or refute the existence of a scientific basis for the Meridian System.
- **Mechanism**: The provided evidence IDs (EV-Q019-dbd9a094a5d8cb07d59d10c8, EV-Q019-64326f42c48d11f37ce04eef, EV-Q019-6d598a0c1126b6c72f64c56b) pertain to computer science keyword extraction, LLM surveys, and socioeconomic research drivers respectively, bearing no semantic or empirical relation to Traditional Chinese Medicine, anatomy, or neurophysiology.
- **Falsifiable Prediction**: If any of the allowed evidence IDs are re-examined and found to contain valid biomedical data regarding meridians or acupuncture mechanisms, this hypothesis of total irrelevance is falsified.
- **Required Observations**: Semantic verification of full text in EV-Q019-dbd9a094a5d8cb07d59d10c8 confirming absence of TCM content；Semantic verification of full text in EV-Q019-64326f42c48d11f37ce04eef confirming absence of TCM content；Semantic verification of full text in EV-Q019-6d598a0c1126b6c72f64c56b confirming absence of TCM content
- **Risk of Being Wrong**: Low risk given explicit metadata and quoted text in evidence extraction; however, hidden sections or supplementary materials in these papers could theoretically contain relevant cross-disciplinary references not captured in current excerpts.

### Hypothesis 2
- **Hypothesis**: Methodological Proxy Hypothesis: Scientific validation of the Meridian System requires distinguishing specific meridian-based effects from non-specific physiological responses, which cannot be tested with current evidence but defines necessary future experimental design.
- **Mechanism**: This hypothesis posits that 'scientific basis' is operationally defined by differential efficacy between true meridian stimulation and sham controls, rather than general acupuncture effects. Since no evidence exists, this serves as a structural prerequisite for future testing rather than a claim about meridian reality.
- **Falsifiable Prediction**: If future studies using rigorous sham-controlled designs consistently show no statistical difference between meridian-specific and non-meridian stimulation for pain modulation, the hypothesis that meridians have a distinct scientific basis is weakened.
- **Required Observations**: Randomized controlled trials comparing true meridian points vs. sham points with identical tactile stimulation；Neuroimaging data showing distinct brain activation patterns for meridian vs. non-meridian stimulation；Biophysical measurements (e.g., electrical conductance) along meridian pathways vs. control pathways
- **Risk of Being Wrong**: High risk as this is a methodological framework without empirical grounding in current evidence; may conflate clinical efficacy with anatomical existence.

## Technical Details
This experiment is designed to rigorously validate the 'Insufficient Evidence Hypothesis' by performing a systematic semantic audit of the provided evidence catalog. The core technical approach involves Natural Language Processing (NLP) techniques, specifically keyword matching and semantic similarity analysis using pre-trained language models (e.g., BERT or SciBERT), to quantify the relevance of the allowed evidence IDs to the domain of Traditional Chinese Medicine (TCM) and Meridian System mechanisms. The process includes: 1) Text extraction from the specified PDFs/URLs associated with EV-Q019-dbd9a094a5d8cb07d59d10c8, EV-Q019-64326f42c48d11f37ce04eef, and EV-Q019-6d598a0c1126b6c72f64c56b. 2) Definition of a TCM-specific lexicon (including terms like 'meridian', 'acupuncture', 'qi', 'jing-luo', 'neurophysiology of acupuncture'). 3) Calculation of cosine similarity between document embeddings and the TCM lexicon vector space. 4) Manual verification of any false positives identified by the algorithm. The hypothesis predicts that similarity scores will be near zero and no substantive content regarding meridian mechanisms will be found.

## Datasets
### Source


```json
[
  {
    "id": "EV-Q019-dbd9a094a5d8cb07d59d10c8",
    "type": "scientific_paper",
    "description": "Full text of arXiv:2207.01888 on Keyword Extraction in Scientific Documents"
  },
  {
    "id": "EV-Q019-64326f42c48d11f37ce04eef",
    "type": "scientific_paper",
    "description": "Full text of arXiv:2406.10833 surveying Scientific LLMs"
  },
  {
    "id": "EV-Q019-6d598a0c1126b6c72f64c56b",
    "type": "scientific_paper",
    "description": "Full text of arXiv:1806.05028 on Socioeconomic driving forces of scientific research"
  }
]
```


### Target


```json
{
  "type": "structured_audit_report",
  "description": "A structured JSON report containing semantic similarity scores, keyword hit counts for TCM-related terms, and binary classification of relevance (Relevant/Irrelevant) for each evidence ID."
}
```


## Paper Abstract
Background: The scientific basis of the Traditional Chinese Medicine Meridian System remains a subject of debate, often conflated with acupuncture efficacy. Objective: To determine if the currently allowed evidence catalog provides any empirical support for meridian mechanisms. Methods: We conducted a semantic audit of three allowed evidence IDs (EV-Q019-dbd9a094a5d8cb07d59d10c8, EV-Q019-64326f42c48d11f37ce04eef, EV-Q019-6d598a0c1126b6c72f64c56b) using SciBERT embeddings and TCM-specific keyword matching. Validation Plan: Double-blind expert review of algorithmic outputs to confirm irrelevance. Results: Pending execution of the semantic audit protocol. Conclusion: Preliminary inspection suggests a complete lack of relevant biomedical data in the allowed sources, necessitating a formal declaration of insufficient evidence rather than mechanistic speculation.

## Methods
1. Data Ingestion: Parse full-text content from URLs associated with the three allowed Evidence IDs. 2. Lexicon Construction: Compile 50+ TCM-specific keywords (e.g., 'meridian', 'jing-luo', 'zang-fu'). 3. Semantic Analysis: Generate document embeddings using SciBERT and compute cosine similarity against the TCM lexicon centroid. 4. Keyword Matching: Perform exact/fuzzy string matching for TCM terms. 5. Verification: Manual review of any positive hits to distinguish substantive content from incidental citations.

## Experiments
### Baselines


```json
[
  "Random Baseline: Generate random vectors of the same dimension as SciBERT embeddings to establish a null distribution for cosine similarity scores.",
  "General Biomedical Baseline: Compute similarity against a general biomedical lexicon (e.g., MeSH terms excluding TCM) to ensure the model distinguishes general medicine from specific TCM concepts."
]
```


### Metrics


```json
[
  "Cosine Similarity Score: Quantitative measure of semantic proximity between evidence documents and TCM concepts.",
  "Keyword Hit Rate: Number of TCM-specific terms found per 1,000 words in each document.",
  "Precision@K: If top-K sentences are retrieved based on relevance, what fraction actually discuss meridian mechanisms? (Expected K=0 for irrelevant docs)."
]
```


### Ablation
Remove the 'medicine' category from the general scientific LLM survey (EV-Q019-64326f42c48d11f37ce04eef) to test if broad mentions of 'medicine' trigger false positives in keyword matching.

### Validation Protocol
Double-blind review: Two independent experts in TCM and biomedical literature review the top 5 most relevant sentences identified by the algorithm for each paper to confirm irrelevance. Inter-rater reliability (Cohen's Kappa) must be > 0.8 to accept the 'Irrelevant' classification.

## Results
当前状态：待执行验证实验。系统已生成可复现实验脚本、数据字段清单与评价指标，尚未运行真实实验。

## References
- **EV-Q019-dbd9a094a5d8cb07d59d10c8** · arxiv · arXiv:2207.01888
  - authors: Not available · year: Not available
  - url: https://arxiv.org/pdf/2207.01888.pdf · doi: Not available
  - reliability_note: eligibility_status=FULLTEXT_VERIFIED; topic_relevance_status=DIRECT_QUESTION_CORE; locator=page:1|section:page-1|paragraph:1; content_sha256=36234e9e444dbb1af65f766f131bc1292a7ead3a9c695e98323e2d44a34ae139
- **EV-Q019-64326f42c48d11f37ce04eef** · arxiv · arXiv:2406.10833
  - authors: Not available · year: Not available
  - url: https://arxiv.org/pdf/2406.10833.pdf · doi: Not available
  - reliability_note: eligibility_status=FULLTEXT_VERIFIED; topic_relevance_status=DIRECT_QUESTION_CORE; locator=page:2|section:page-2|paragraph:1; content_sha256=e7643f7b8fce449a0cd175462b8e87019f97d7b2fda5cabe4240cd53605bad64
- **EV-Q019-6d598a0c1126b6c72f64c56b** · arxiv · arXiv:1806.05028
  - authors: Not available · year: Not available
  - url: https://arxiv.org/pdf/1806.05028.pdf · doi: Not available
  - reliability_note: eligibility_status=FULLTEXT_VERIFIED; topic_relevance_status=DIRECT_QUESTION_CORE; locator=page:1|section:page-1|paragraph:1; content_sha256=b9108b9779e455f59fed60bb2a129ffb77923f176a0bd38a429f1d19295f32db

## Reviewer Comments
- The candidate hypothesis correctly identifies 'insufficient_evidence' given that all allowed evidence IDs pertain to computer science or scientometrics rather than Traditional Chinese Medicine.
- Experiment design appropriately pivots to a meta-validation protocol (semantic audit) to verify the irrelevance of the provided evidence, which is the only scientifically valid action under current constraints.
- Results field is correctly marked as pending/not executed, avoiding fabrication.
- No causal claims are made regarding meridian mechanisms; the output strictly adheres to the negative constraint imposed by the evidence catalog.
- References in datasets.source match the allowed evidence_ids exactly.

## Revision History

## Reproducibility Checklist
- Verify access to full-text PDFs for all three Evidence IDs via provided URLs.
- Ensure SciBERT or equivalent transformer model is available for embedding generation.
- Document the exact TCM lexicon used for keyword matching.
- Save raw cosine similarity scores and keyword hit counts for each document.
- Archive manual review annotations for inter-rater reliability calculation.

