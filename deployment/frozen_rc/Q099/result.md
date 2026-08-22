# Structural Misalignment: A Gap Analysis Between Computational Models of Digital Addiction and Societal Burden Metrics

## Input Question
What is addiction and how does it work?

## Domain
Neuroscience

## Validation Status
needs_data

## Problem Statement
The U.S. National Institute on Drug Abuse (NIH) defines addiction as a chronic, relapsing disorder characterized by compulsive drug seeking and long-lasting brain changes affecting inhibition, reward, and decision-making. However, the provided evidence base consists primarily of computational models of digital addiction (e.g., auctions, short-videos) and societal burden statistics, lacking direct neurobiological mechanistic data. The core problem is to determine how current computational conceptualizations of addiction align with or diverge from the severity dimensions implied by clinical burden data, given the absence of direct neural evidence in the allowed corpus.

## Rationale
Since direct neurobiological mechanisms are not present in the allowed evidence IDs, this research plan reframes the question to analyze the structural consistency between computational models of addictive behaviors (EV-Q099-f2c4c61b7491ac6dbbe03e74, EV-Q099-7556a928fd6b02150f4e35de) and the societal harm metrics associated with substance misuse (EV-Q099-2f1a6d91fbb53a21d1fbe2d6). This approach allows for a rigorous, evidence-grounded analysis of 'how addiction works' within the constraints of the available literature, identifying critical gaps between engagement optimization and clinical harm.

## Generated Hypotheses

### Hypothesis 1
- **Hypothesis**: Current computational models of digital addiction (EV-Q099-f2c4c61b7491ac6dbbe03e74, EV-Q099-7556a928fd6b02150f4e35de) are structurally insufficient to account for the severity dimension of addiction implied by societal burden data (EV-Q099-2f1a6d91fbb53a21d1fbe2d6), as they optimize for engagement metrics that lack formal mapping to clinical harm or mortality drivers.
- **Mechanism**: Evidence EV-Q099-2f1a6d91fbb53a21d1fbe2d6 establishes that addiction entails severe outcomes (>100k deaths/year, billions in costs). Evidence EV-Q099-f2c4c61b7491ac6dbbe03e74 and EV-Q099-7556a928fd6b02150f4e35de provide computational mechanisms optimizing for participation/engagement. A critical Knowledge Gap exists: no allowed evidence links these computational engagement parameters to the clinical severity or mortality drivers cited in the burden literature. This hypothesis posits that the objective functions in current CS models are orthogonal to the variables driving the societal burden, rendering them descriptive of platform usage but not explanatory of the 'chronic, relapsing disorder' defined by harm.
- **Falsifiable Prediction**: If a systematic parameter audit reveals that the engagement optimization variables in EV-Q099-f2c4c61b7491ac6dbbe03e74 and EV-Q099-7556a928fd6b02150f4e35de explicitly incorporate constraints or cost functions corresponding to the healthcare/mortality drivers described in EV-Q099-2f1a6d91fbb53a21d1fbe2d6, then the structural insufficiency hypothesis is false.
- **Required Observations**: Formal extraction of objective functions and state variables from EV-Q099-f2c4c61b7491ac6dbbe03e74 and EV-Q099-7556a928fd6b02150f4e35de.；Semantic mapping analysis comparing extracted computational variables against the specific harm/cost descriptors in EV-Q099-2f1a6d91fbb53a21d1fbe2d6.；Verification of whether any cited references within the computational papers bridge the gap to clinical severity metrics.
- **Risk of Being Wrong**: Moderate risk; the computational papers might implicitly model severity through proxy variables (e.g., 'retention under negative feedback') that align with burden drivers, even if not explicitly labeled as 'mortality' or 'healthcare cost'.

### Hypothesis 2
- **Hypothesis**: Computational models of short-video and auction addiction (EV-Q099-f2c4c61b7491ac6dbbe03e74, EV-Q099-7556a928fd6b02150f4e35de) exhibit convergent structural properties in reward scheduling that distinguish them from standard engagement optimization, representing a distinct 'computational phenotype' of addiction within the CS literature independent of neurobiological validation.
- **Mechanism**: While neurobiological validation is absent (Knowledge Gap), the CS literature itself may define addiction operationally. If EV-Q099-f2c4c61b7491ac6dbbe03e74 and EV-Q099-7556a928fd6b02150f4e35de share specific algorithmic motifs (e.g., variable-ratio reinforcement, feedback loop latency) that differ from generic recommendation systems (referenced in EV-Q099-094f5c0c88dcd7c61f92708f), this suggests an internal theoretical consistency in how CS conceptualizes 'addiction' as a computational process. This hypothesis tests the internal validity of the CS construct rather than its external clinical validity.
- **Falsifiable Prediction**: If the algorithmic parameters for 'addiction' in EV-Q099-f2c4c61b7491ac6dbbe03e74 and EV-Q099-7556a928fd6b02150f4e35de are statistically indistinguishable from standard engagement metrics in general user behavior models (EV-Q099-094f5c0c88dcd7c61f92708f), then there is no distinct 'computational addiction phenotype' in the provided literature.
- **Required Observations**: Comparative code/model specification analysis between the 'addiction' focused papers and general behavior papers.；Quantification of specific reward schedule parameters (e.g., probability distributions, decay rates) across the three evidence sources.；Clustering analysis to determine if 'addiction' models form a distinct group based on architectural features.
- **Risk of Being Wrong**: High risk; the papers may use identical underlying RL architectures with only superficial labeling differences, meaning 'addiction' in CS is merely a semantic tag rather than a structural distinction.

### Hypothesis 3
- **Hypothesis**: The definition of addiction in the provided computational literature is exclusively operationalized via participation maximization, creating a fundamental epistemic mismatch with the 'harm-based' definition implied by societal burden evidence (EV-Q099-2f1a6d91fbb53a21d1fbe2d6).
- **Mechanism**: This hypothesis reframes the question 'how does it work' to 'how is it modeled vs. how is it burdened'. It posits that the mechanism of action in CS papers (EV-Q099-f2c4c61b7491ac6dbbe03e74, EV-Q099-7556a928fd6b02150f4e35de) is strictly positive-reinforcement driven (participation/lucky-draw), whereas the burden evidence (EV-Q099-2f1a6d91fbb53a21d1fbe2d6) implies a negative-outcome driven mechanism (death/cost). The 'working' of addiction in CS is thus hypothesized to be the inverse of its 'working' in public health contexts.
- **Falsifiable Prediction**: If the computational models explicitly include negative utility terms, safety constraints, or harm-minimization objectives alongside participation metrics, then the exclusive operationalization hypothesis is false.
- **Required Observations**: Text mining and mathematical formulation extraction from EV-Q099-f2c4c61b7491ac6dbbe03e74 and EV-Q099-7556a928fd6b02150f4e35de to identify all objective function components.；Categorization of identified components as 'participation-promoting' vs. 'harm-mitigating'.；Cross-reference with burden drivers in EV-Q099-2f1a6d91fbb53a21d1fbe2d6 to check for alignment.
- **Risk of Being Wrong**: Low risk; it is highly probable that CS papers focus on engagement, but there is a non-zero chance that ethical AI or safe RL frameworks have been integrated into these specific preprints.

## Technical Details
This study conducts a structural gap analysis to test the hypothesis that current computational models of digital addiction (EV-Q099-f2c4c61b7491ac6dbbe03e74, EV-Q099-7556a928fd6b02150f4e35de) are structurally insufficient to account for the severity dimension of addiction implied by societal burden data (EV-Q099-2f1a6d91fbb53a21d1fbe2d6). The methodology involves: 1) Formal extraction of objective functions, state variables, and optimization targets from the computational models in EV-Q099-f2c4c61b7491ac6dbbe03e74 (short-video feedback loops) and EV-Q099-7556a928fd6b02150f4e35de (lucky-draw/auction mechanisms). 2) Semantic mapping of these computational variables against the specific harm/cost descriptors (e.g., healthcare spending, mortality drivers) identified in EV-Q099-2f1a6d91fbb53a21d1fbe2d6. 3) Verification of whether any cited references within the computational papers bridge the gap to clinical severity metrics. The core technical challenge is defining a 'structural alignment metric' that quantifies the presence or absence of harm-mitigation constraints or severity-correlated variables in the engagement-optimization algorithms. This approach avoids ungrounded neurobiological claims and synthetic clinical benchmarks, focusing strictly on the internal consistency and external validity of the provided evidence set.

## Datasets
### Source


```json
[
  {
    "name": "Computational Model Specifications",
    "description": "Extraction of algorithmic parameters, objective functions, and reward structures from EV-Q099-f2c4c61b7491ac6dbbe03e74 and EV-Q099-7556a928fd6b02150f4e35de.",
    "evidence_ids": [
      "EV-Q099-f2c4c61b7491ac6dbbe03e74",
      "EV-Q099-7556a928fd6b02150f4e35de"
    ],
    "type": "model_specification"
  },
  {
    "name": "Societal Burden Descriptors",
    "description": "Extraction of specific harm indicators (mortality, healthcare costs) and their drivers as described in EV-Q099-2f1a6d91fbb53a21d1fbe2d6.",
    "evidence_ids": [
      "EV-Q099-2f1a6d91fbb53a21d1fbe2d6"
    ],
    "type": "textual_evidence"
  }
]
```


### Target


```json
{
  "name": "Structural Alignment Matrix",
  "description": "A binary or weighted matrix indicating whether each computational variable in the source models has a corresponding counterpart in the societal burden descriptors.",
  "type": "derived_analysis"
}
```


## Paper Abstract
Background: Addiction is defined by the NIH as a chronic, relapsing disorder with severe societal consequences, including significant healthcare costs and mortality. While computational models increasingly simulate addictive behaviors in digital contexts (e.g., short-videos, auctions), it remains unclear whether these models capture the severity dimensions inherent in clinical definitions. Methods: We performed a structural gap analysis comparing objective functions and state variables from computational models of digital addiction (EV-Q099-f2c4c61b7491ac6dbbe03e74, EV-Q099-7556a928fd6b02150f4e35de) against societal burden descriptors derived from public health data (EV-Q099-2f1a6d91fbb53a21d1fbe2d6). We developed a Structural Alignment Matrix to quantify the presence of harm-mitigation constraints or severity-correlated variables in engagement-optimization algorithms. Validation Plan: The study tests the falsifiable prediction that current computational models lack explicit mappings to clinical harm drivers. Results: pending. This analysis aims to identify epistemic gaps between computational engagement metrics and clinical severity, informing the development of more ethically aligned and clinically valid models of addictive behavior.

## Methods
1. Text Mining & Parameter Extraction: Use NLP techniques to identify mathematical formulations and key variables (e.g., 'participation rate', 'lucky-draw probability', 'retention time') in EV-Q099-f2c4c61b7491ac6dbbe03e74 and EV-Q099-7556a928fd6b02150f4e35de. 2. Semantic Ontology Mapping: Create a controlled vocabulary of 'harm drivers' from EV-Q099-2f1a6d91fbb53a21d1fbe2d6 (e.g., 'mortality', 'healthcare cost', 'relapse severity'). 3. Gap Analysis: Systematically check if any extracted computational variable explicitly optimizes for, constrains, or correlates with the harm drivers. 4. Citation Network Analysis: Verify if the computational papers cite clinical literature that establishes this link.

## Experiments
### Baselines


```json
[
  "Null Model: Assumes no alignment between computational variables and harm drivers (expected outcome if hypothesis is true).",
  "General Engagement Model: A baseline representation of standard recommendation systems (referenced in EV-Q099-094f5c0c88dcd7c61f92708f if applicable, or generic RL) to contrast with 'addiction-specific' claims."
]
```


### Metrics


```json
[
  "Variable-Harm Coverage Score: Percentage of harm drivers from EV-Q099-2f1a6d91fbb53a21d1fbe2d6 that have a direct mapping in the computational models' objective functions.",
  "Explicit Constraint Count: Number of explicit safety/harm-minimization terms found in the mathematical formulations of EV-Q099-f2c4c61b7491ac6dbbe03e74 and EV-Q099-7556a928fd6b02150f4e35de.",
  "Citation Bridge Index: Binary indicator of whether the computational papers cite sources that link their specific engagement metrics to clinical severity outcomes."
]
```


### Ablation
Remove the 'addiction' labeling from the computational models and treat them as standard optimization problems to see if the structural properties change; if not, it suggests the 'addiction' label is semantic rather than mechanistic.

### Validation Protocol
Peer review of the semantic mapping ontology to ensure no forced correlations. Cross-checking extracted equations against the original PDFs for accuracy. Sensitivity analysis on the definition of 'harm driver' to ensure robustness of the gap finding.

## Results
当前状态：待执行验证实验。系统已生成可复现实验脚本、数据字段清单与评价指标，尚未运行真实实验。

## References
- **EV-Q099-7556a928fd6b02150f4e35de** · arxiv · arXiv:1906.03237
  - authors: Not available · year: Not available
  - url: https://arxiv.org/pdf/1906.03237.pdf · doi: Not available
  - reliability_note: eligibility_status=FULLTEXT_VERIFIED; topic_relevance_status=DIRECT_QUESTION_CORE; locator=page:1|section:page-1|paragraph:1; content_sha256=3950b993a4dddc9a2a6ca01321bd4a73f1f0235ab49a68e8e011d119af920ce1
- **EV-Q099-094f5c0c88dcd7c61f92708f** · arxiv · arXiv:2304.06630
  - authors: Not available · year: Not available
  - url: https://arxiv.org/pdf/2304.06630.pdf · doi: Not available
  - reliability_note: eligibility_status=FULLTEXT_VERIFIED; topic_relevance_status=DIRECT_QUESTION_CORE; locator=page:8|section:page-8|paragraph:1; content_sha256=e049f1f36d5d7d9cd1db0a6d0ae4a3d48442c423f6a0da4f12a03dae37e7e6c7
- **EV-Q099-f2c4c61b7491ac6dbbe03e74** · arxiv · arXiv:2601.15975
  - authors: Not available · year: Not available
  - url: https://arxiv.org/pdf/2601.15975.pdf · doi: Not available
  - reliability_note: eligibility_status=FULLTEXT_VERIFIED; topic_relevance_status=DIRECT_QUESTION_CORE; locator=page:1|section:page-1|paragraph:1; content_sha256=185106be1740c98160003e5bc6d9ed45a65048a7f4ff938e7c77417e7421690c
- **EV-Q099-2f1a6d91fbb53a21d1fbe2d6** · arxiv · arXiv:2407.16987
  - authors: Not available · year: Not available
  - url: https://arxiv.org/pdf/2407.16987.pdf · doi: Not available
  - reliability_note: eligibility_status=FULLTEXT_VERIFIED; topic_relevance_status=DIRECT_QUESTION_CORE; locator=page:2|section:page-2|paragraph:1; content_sha256=f412ca26c7288792104224462efe671a06bd4892fc51e865ba38fddc2b692724

## Reviewer Comments
- The revised hypothesis successfully reframes the investigation as a structural gap analysis between computational models (EV-Q099-f2c4c61b7491ac6dbbe03e74, EV-Q099-7556a928fd6b02150f4e35de) and societal burden evidence (EV-Q099-2f1a6d91fbb53a21d1fbe2d6), eliminating all ungrounded neurobiological claims.
- The 'Synthetic Clinical Benchmarks' dataset has been correctly removed and replaced with a 'Structural Alignment Matrix' derived strictly from allowed evidence IDs, resolving the critical issue of non-evidence-based ground truth.
- The falsifiable prediction is now logically sound within the system constraints: it tests for the presence/absence of specific semantic mappings between model parameters and burden descriptors, making it verifiable without external clinical data.
- The Results field correctly remains 'pending', and the experimental design includes appropriate baselines (Null Model, General Engagement Model) and metrics (Variable-Harm Coverage Score) that directly operationalize the revised hypothesis.

## Revision History
- auto_revision_1: 依据评审意见重做假设与实验设计。

## Reproducibility Checklist
- Extraction scripts for mathematical formulations from arXiv PDFs are version-controlled.
- Semantic ontology for harm drivers is documented and open for review.
- Mapping logic between computational variables and harm descriptors is explicitly defined and deterministic.
- Citation network analysis uses standard bibliometric tools.

