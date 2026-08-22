# Validation of Evidence Absence: Characterizing Retrieval Artifacts in AI Literature Regarding Human Handedness

## Input Question
Why are most people right-handed?

## Domain
Neuroscience

## Validation Status
needs_data

## Problem Statement
The provided booklet excerpt states that 85%–90% of humans are right-handed but explicitly notes there is no simple reason why. The core scientific problem is to identify the underlying biological, genetic, or evolutionary mechanisms driving this population-level lateralization, given that the current evidence set contains no direct neuroscientific data on handedness.

## Rationale
Understanding the etiology of handedness is fundamental to neuroscience and developmental biology. However, the allowed evidence catalog consists entirely of papers on AI fairness, accessibility, and social event recognition. Therefore, the immediate scientific task is not to propose a biological mechanism (which would be unsupported speculation) but to rigorously validate the absence of relevant evidence in the provided corpus and characterize the retrieval artifacts that assigned high relevance scores to unrelated AI literature.

## Generated Hypotheses

### Hypothesis 1
- **Hypothesis**: Evidence Absence Null Hypothesis: The allowed evidence set contains no biological, genetic, or evolutionary data explaining human right-handedness; observed high relevance scores are retrieval artifacts unrelated to topical validity.
- **Mechanism**: The four allowed Evidence IDs (EV-Q102-c40e40012d0153a82cbf942b, EV-Q102-9134ca6c0ed671edc59af966, EV-Q102-dd2cdb145d3e1bdde7573b59, EV-Q102-00ebc1e7ba82944f22d42e38) exclusively address AI fairness, accessibility technology, and social event recognition. No card contains factual assertions regarding neuroanatomy, genetics, or evolutionary biology relevant to handedness. The high relevance_score (0.75–0.95) assigned to these papers is a retrieval system artifact resulting from keyword overlap (e.g., 'disability', 'human-centered') rather than semantic alignment with the neuroscience question. Therefore, any causal mechanism for right-handedness derived solely from this evidence set would be ungrounded speculation. This hypothesis validates the absence of evidence in the current corpus, not the biological non-existence of handedness mechanisms.
- **Falsifiable Prediction**: A comprehensive full-text semantic search of all four allowed Evidence IDs using an expanded lexicon including 'right-handed', 'left-handed', 'manual asymmetry', 'lateralization', and 'motor cortex' will yield zero biologically relevant mentions. Any detected instances will be confirmed as non-biological (e.g., spatial references in computer vision) upon manual context verification.
- **Required Observations**: Full-text extraction and keyword search of EV-Q102-c40e40012d0153a82cbf942b confirming topic is elderly travel assistance AI with no handedness content；Full-text extraction and keyword search of EV-Q102-9134ca6c0ed671edc59af966 confirming topic is social event image recognition with no handedness content；Full-text extraction and keyword search of EV-Q102-dd2cdb145d3e1bdde7573b59 confirming topic is AI ethics/disability accessibility with no handedness content；Full-text extraction and keyword search of EV-Q102-00ebc1e7ba82944f22d42e38 confirming topic is AI fairness for deaf/hard-of-hearing with no handedness content；Manual verification that any keyword hits are false positives (e.g., 'left-hand side of UI') rather than biological discussions
- **Risk of Being Wrong**: Low risk. The evidence extraction metadata explicitly states 'insufficient_evidence' and quoted_text excerpts show no biological content. If any allowed ID contains genuine neuroscientific discussion of handedness (e.g., as a case study in motor accessibility), this hypothesis is immediately falsified. However, current metadata and excerpts strongly suggest irrelevance.

### Hypothesis 2
- **Hypothesis**: Retrieval Artifact Hypothesis: High relevance scores (0.75–0.95) for AI-focused papers in response to a neuroscience question indicate systematic failure in semantic filtering, where keyword-based matching on terms like 'disability' or 'human' produces false positives that must be algorithmically distinguished from true topical relevance.
- **Mechanism**: The evidence catalog assigns high relevance_score values to papers on AI accessibility (EV-Q102-dd2cdb145d3e1bdde7573b59, EV-Q102-00ebc1e7ba82944f22d42e38) despite quoted_text showing no connection to handedness biology. This discrepancy suggests the retrieval system matched surface-level keywords ('disability', 'accessibility', 'human-centered') without validating semantic alignment to the neuroscientific query. The mechanism is a lexical-semantic gap in the retrieval pipeline that conflates general human-related AI research with specific biological traits. This hypothesis treats the retrieval error itself as a testable phenomenon distinct from the biological question.
- **Falsifiable Prediction**: Re-running evidence retrieval with strict semantic filtering for 'biological basis of handedness' OR 'manual asymmetry etiology' will reduce relevance_score of all four current allowed IDs below 0.1 AND return zero qualified evidence cards. Alternatively, if manual curation confirms any ID was correctly tagged as relevant, the artifact hypothesis is weakened.
- **Required Observations**: Quantitative comparison of original vs. refined semantic query results showing score reduction；Keyword overlap analysis demonstrating 'disability'/'accessibility' drove initial matches while 'handedness'/'lateralization' were absent；Verification that locator field 'topic_relevance_status=DIRECT_QUESTION_CORE' was assigned algorithmically without manual validation；Confirmation that no allowed ID discusses handedness even as an accessibility use case
- **Risk of Being Wrong**: Moderate risk. One or more AI papers might discuss handedness as a bias factor in interface design or as a demographic variable in accessibility studies, which would maintain partial relevance. However, quoted_text excerpts provide no indication of such content, making this unlikely.

## Technical Details
This experiment validates the 'Evidence Absence Null Hypothesis' by performing a deterministic full-text semantic audit of the four allowed Evidence IDs. The technical pipeline involves: (1) PDF text extraction from the provided arXiv URLs for EV-Q102-c40e40012d0153a82cbf942b, EV-Q102-9134ca6c0ed671edc59af966, EV-Q102-dd2cdb145d3e1bdde7573b59, and EV-Q102-00ebc1e7ba82944f22d42e38; (2) Application of an expanded biological lexicon including 'right-handed', 'left-handed', 'manual asymmetry', 'lateralization', 'motor cortex', and 'handedness'; (3) Contextual verification to distinguish biological usage from spatial/UI references (e.g., 'left-hand side'); and (4) Explicit documentation that high relevance scores (0.75–0.95) are retrieval artifacts driven by keyword overlap (e.g., 'disability', 'human-centered') rather than topical validity for handedness research. A mandatory disclaimer is included stating that this validation confirms the absence of evidence in the current corpus, not the biological non-existence of handedness mechanisms.

## Datasets
### Source


```json
[
  "EV-Q102-c40e40012d0153a82cbf942b",
  "EV-Q102-9134ca6c0ed671edc59af966",
  "EV-Q102-dd2cdb145d3e1bdde7573b59",
  "EV-Q102-00ebc1e7ba82944f22d42e38"
]
```


### Target
Binary presence/absence matrix of biological handedness terminology within each Evidence ID, annotated with context classification (Biological vs. Non-Biological/Artifact).

## Paper Abstract
Background: While 85%-90% of humans are right-handed, the biological mechanisms remain complex. This study addresses the epistemic constraint where available evidence catalogs may contain retrieval artifacts rather than relevant neuroscientific data. Methods: We performed a full-text semantic audit of four high-relevance AI papers (arXiv:2607.21156, arXiv:1904.03632, arXiv:1907.02227, arXiv:1908.10414) using an expanded lexicon ('right-handed', 'lateralization', 'manual asymmetry'). Verification Protocol: Keyword hits were manually contextualized to distinguish biological references from spatial/UI artifacts. Pending Results: Experimental execution is pending; we hypothesize zero biological relevance, confirming the evidence set's insufficiency for answering the core neuroscience question.

## Methods
1. Text Extraction: Parse full-text PDFs from the allowed Evidence IDs using PyPDF2/pdfplumber. 2. Lexicon Search: Execute case-insensitive search for the expanded lexicon: ['right-handed', 'left-handed', 'manual asymmetry', 'lateralization', 'motor cortex', 'handedness', 'hemisphere dominance']. 3. Artifact Filtering: Flag any hits containing spatial terms (e.g., 'left side of image', 'right-hand column') as non-biological false positives. 4. Relevance Score Analysis: Correlate the original high relevance scores (0.75–0.95) with the absence of biological keywords to demonstrate retrieval artifact status. 5. Manual Verification: Double-blind review of any potential matches to confirm irrelevance to neurobiology.

## Experiments
### Baselines


```json
[
  "Random Neuroscience Control: 4 random arXiv papers from the 'Neuroscience' category to verify the lexicon successfully detects biological handedness content when present.",
  "Keyword-Only Retrieval Baseline: Replicate the original retrieval logic using only surface-level keyword matching (e.g., 'disability', 'human') to demonstrate how these AI papers achieved high relevance scores despite lacking biological content."
]
```


### Metrics


```json
[
  "Hit Rate: Percentage of allowed Evidence IDs containing at least one biological handedness term (Expected: 0%).",
  "Precision of Biological Context: Ratio of true biological mentions to total keyword hits (Expected: 0 or undefined).",
  "Semantic Distance: Cosine similarity between document embeddings and a canonical 'handedness mechanism' query vector (Expected: Low, indicating topical divergence)."
]
```


### Ablation
Remove general directional terms ('left', 'right') from the search lexicon to isolate specific biological terms ('manual asymmetry', 'lateralization') and prevent false positives from UI/spatial descriptions in AI papers.

### Validation Protocol
If any keyword hit is detected, two independent annotators must verify the context. If the context is non-biological (e.g., computer vision spatial reference), it is classified as a false positive. The hypothesis is supported if all hits are false positives or zero hits are found. The final report must explicitly state that high relevance scores are retrieval artifacts.

## Results
当前状态：待执行验证实验。系统已生成可复现实验脚本、数据字段清单与评价指标，尚未运行真实实验。

## References
- **EV-Q102-c40e40012d0153a82cbf942b** · arxiv · arXiv:2607.21156
  - authors: Not available · year: Not available
  - url: https://arxiv.org/pdf/2607.21156.pdf · doi: Not available
  - reliability_note: eligibility_status=FULLTEXT_VERIFIED; topic_relevance_status=DIRECT_QUESTION_CORE; locator=page:1|section:page-1|paragraph:1; content_sha256=421caaa5f952f600028287b369562c0bee0c9ddfe18291bbc3450338b094626d
- **EV-Q102-9134ca6c0ed671edc59af966** · arxiv · arXiv:1904.03632
  - authors: Not available · year: Not available
  - url: https://arxiv.org/pdf/1904.03632.pdf · doi: Not available
  - reliability_note: eligibility_status=FULLTEXT_VERIFIED; topic_relevance_status=DIRECT_QUESTION_CORE; locator=page:2|section:page-2|paragraph:1; content_sha256=3c14b66a1e2a0bc21c0fbb982c7acdfe826aff90b679f3bb18232a1db50f5500
- **EV-Q102-dd2cdb145d3e1bdde7573b59** · arxiv · arXiv:1907.02227
  - authors: Not available · year: Not available
  - url: https://arxiv.org/pdf/1907.02227.pdf · doi: Not available
  - reliability_note: eligibility_status=FULLTEXT_VERIFIED; topic_relevance_status=DIRECT_QUESTION_CORE; locator=page:1|section:page-1|paragraph:1; content_sha256=7930fabc93c3df016bc992b622b195ce04b2e3034326735fa9b9568fe8d308b0
- **EV-Q102-00ebc1e7ba82944f22d42e38** · arxiv · arXiv:1908.10414
  - authors: Not available · year: Not available
  - url: https://arxiv.org/pdf/1908.10414.pdf · doi: Not available
  - reliability_note: eligibility_status=FULLTEXT_VERIFIED; topic_relevance_status=DIRECT_QUESTION_CORE; locator=page:1|section:page-1|paragraph:1; content_sha256=6d76837fab6f6fa1ca34b8e22bba1b76ec982e9f64fc91333dc96e3d99500729

## Reviewer Comments
- Revision 2 successfully incorporates all required revisions from the previous review cycle.
- The hypothesis mechanism now explicitly identifies high relevance scores (0.75-0.95) as retrieval artifacts driven by keyword overlap rather than topical validity, satisfying revision request 1a92b6861e94.
- The experimental lexicon has been correctly expanded to include 'right-handed', 'left-handed', and 'manual asymmetry' as verified in the methods section, satisfying revision request 06c20200481c.
- The mandatory disclaimer distinguishing evidence absence from biological non-existence is present in both the hypothesis mechanism and technical_details, satisfying revision request 30f888051c7b.
- No fabricated results detected; Results field correctly remains 'pending'.
- All supporting evidence IDs are valid and strictly limited to the allowed catalog.
- Experiment design includes appropriate baselines (Random Neuroscience Control) to validate the null result methodology.

## Revision History
- auto_revision_1: 依据评审意见重做假设与实验设计。

## Reproducibility Checklist
- Verify full-text access to all four arXiv PDFs via provided URLs.
- Confirm the expanded keyword lexicon includes 'right-handed', 'left-handed', and 'manual asymmetry'.
- Document the explicit disclaimer that evidence absence ≠ biological non-existence.
- Log all keyword hits with line numbers and context snippets for manual review.
- Store raw text extracts and search logs in a version-controlled repository.
- Explicitly label high relevance scores (0.75–0.95) as retrieval artifacts in the final output.

