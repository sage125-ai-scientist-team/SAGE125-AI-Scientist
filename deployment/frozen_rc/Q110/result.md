# Ex-Post Illusion: Testing Methodological Bias in Catastrophic Weather Event Prediction via Cross-Domain Transfer from Legal Analytics

## Input Question
Will we be able to predict catastrophic weather events (tsunamis, hurricanes, earthquakes) more accurately?

## Domain
Ecology

## Validation Status
needs_data

## Problem Statement
The precise prediction of sudden damaging events such as earthquakes, tropical cyclones, and tsunamis remains an unsolved problem despite advancements in hardware and algorithms. The core scientific challenge is determining whether current predictive capabilities are limited by technological deficits or by methodological biases in how models are validated against historical data.

## Rationale
Direct evidence on geophysical prediction accuracy is absent from the allowed evidence catalog. However, EV-Q110-caa38ce124360ec0211bccc2 identifies a critical methodological distinction in predictive modeling: the difference between 'ex-post' explanation of decided cases and 'ex-ante' prediction of future events. This research plan hypothesizes that geophysical forecasting may suffer from similar 'ex-post bias,' where models are optimized for retrospective fit rather than prospective accuracy. By transferring this epistemological framework from legal analytics to geophysics, we can test if reported prediction accuracies are inflated by methodological artifacts rather than genuine physical insight.

## Generated Hypotheses

### Hypothesis 1
- **Hypothesis**: Cross-Domain Methodological Transfer Hypothesis: Geophysical forecasting evaluation protocols exhibit the same 'ex-post bias' patterns identified in legal analytics (EV-Q110-caa38ce124360ec0211bccc2), such that reported predictive skill for catastrophic weather events is systematically inflated by retrospective fitting to decided cases rather than genuine ex-ante capability.
- **Mechanism**: This hypothesis treats the distinction between 'ex-post explanation of decided cases' and 'ex-ante prediction of future events' established in legal modeling literature (EV-Q110-caa38ce124360ec0211bccc2) as a transferable methodological framework. It posits that if geophysical forecasting research has adopted similar validation norms (e.g., random temporal splitting, post-hoc parameter tuning on extreme events), then current accuracy metrics reflect overfitting to historical catastrophes ('decided cases') rather than robust predictive power. The mechanism is not physical but epistemological: the lack of strict temporal separation in model validation creates an illusion of progress analogous to that observed in legal case prediction.
- **Falsifiable Prediction**: If this hypothesis is correct, a systematic audit of top-cited geophysical forecasting papers will reveal that >50% employ validation protocols permitting look-ahead bias (e.g., non-chronological splits, leakage of event-specific parameters). Furthermore, re-evaluating these models under strict ex-ante protocols (training strictly on t<T, testing on t>=T) will result in a statistically significant drop in skill scores (>20%) compared to originally reported values. If no such drop occurs or if ex-post/ex-ante definitions are already rigorously distinguished in geophysics, the transfer hypothesis is falsified.
- **Required Observations**: Quantitative coding of validation methodologies in top-100 cited catastrophic weather prediction papers (2018-2024) classifying them as 'Ex-Post Permissive' vs 'Ex-Ante Strict'；Reproduction of at least 3 representative models using identical architectures but with strict chronological train/test splits；Comparison of original reported skill scores vs. re-evaluated ex-ante skill scores；Citation analysis correlating methodological rigor with publication impact
- **Risk of Being Wrong**: Primary risk is Domain Transferability Failure: Geophysical systems may possess sufficient stationarity and physical constraints such that ex-post fitting is a valid proxy for ex-ante skill, unlike socio-legal systems. The 'ex-post/ex-ante' distinction from EV-Q110-caa38ce124360ec0211bccc2 may be ontologically irrelevant to deterministic chaotic systems. Additionally, the geophysical community may have already solved this methodological issue independently, making the legal analogy redundant.

### Hypothesis 2
- **Hypothesis**: Epistemological Category Error Hypothesis: Current limitations in predicting single catastrophic weather events stem from a 'category error' analogous to the ABL rule violation (EV-Q110-59bd19cd52176b237456294d), where ensemble-level statistical observables are erroneously treated as deterministic predictors for individual system instances.
- **Mechanism**: Drawing a conceptual parallel from quantum measurement theory (EV-Q110-59bd19cd52176b237456294d), this hypothesis proposes that geophysical forecasting suffers from confusing properties that only emerge in physical ensembles (e.g., climatological frequencies, regional hazard rates) with observables belonging to a single specific event instance. If this category error exists, increasing observational resolution (hardware) cannot resolve prediction gaps because the probabilistic measure is applied to the wrong ontological level. This reframes the 'unsolved problem' as a fundamental epistemological mismatch rather than a technological deficit.
- **Falsifiable Prediction**: If this hypothesis is correct, predictive models constructed using strictly single-system observables (excluding ensemble-derived priors like seasonal averages or regional seismicity rates) should demonstrate equal or superior ex-ante skill for individual extreme events compared to standard ensemble-informed models. Conversely, if ensemble-derived features consistently provide unique predictive signal for individual events that single-system variables cannot capture, the category error analogy is falsified.
- **Required Observations**: Formal definition and operationalization of 'single-system' vs 'ensemble' observables in geophysical forecast codebases；Comparative hindcast skill scores of single-event vs. ensemble-derived feature sets on historical tsunami/earthquake/cyclone catalogs；Statistical independence tests between ensemble priors and single-event outcomes；Theoretical analysis of ergodicity assumptions in current geophysical models
- **Risk of Being Wrong**: High risk of Mathematical Invalidity: The analogy between quantum mechanical measurement theory (ABL rule) and macroscopic geophysical forecasting may be fundamentally flawed. Geophysical chaos differs from quantum probability; ensemble statistics may be legitimately applicable to single events via ergodic assumptions in classical dynamical systems. The 'category error' may be a feature of quantum ontology, not a universal epistemological constraint.

## Technical Details
This experiment tests the 'Cross-Domain Methodological Transfer Hypothesis' by investigating whether geophysical forecasting evaluation protocols exhibit 'ex-post bias' patterns analogous to those identified in legal analytics (EV-Q110-caa38ce124360ec0211bccc2). The study does not assume physical equivalence but treats the methodological distinction between 'ex-post explanation of decided cases' and 'ex-ante prediction of future events' as a transferable epistemological framework. The experiment consists of two phases: (1) A preliminary validation step involving a systematic audit of top-cited geophysical forecasting literature to verify if the 'ex-post/ex-ante' distinction is explicitly recognized or if validation protocols permit look-ahead bias; (2) A comparative modeling experiment where representative spatiotemporal models are re-evaluated under strict ex-ante protocols (chronological splitting) versus standard ex-post protocols (random splitting) to quantify potential performance inflation. Domain transferability is explicitly treated as a primary risk and knowledge gap.

## Datasets
### Source


```json
[
  "IBTrACS (International Best Track Archive for Climate Stewardship) for historical tropical cyclone tracks",
  "ERA5 Reanalysis Data for atmospheric variables",
  "Web of Science/Scopus metadata for meta-analysis of validation methodologies in disaster prediction papers (2018-2024)"
]
```


### Target
Comparative skill scores (Brier, AUPRC) under ex-ante vs. ex-post validation regimes; Classification of literature validation protocols as 'Ex-Post Permissive' or 'Ex-Ante Strict'.

## Paper Abstract
Background: Predicting catastrophic events like tsunamis and hurricanes remains an unsolved challenge. While hardware and algorithms have advanced, it is unclear if reported improvements reflect genuine predictive capability or methodological artifacts. Methods: Drawing on the distinction between 'ex-post explanation' and 'ex-ante prediction' identified in legal analytics (EV-Q110-caa38ce124360ec0211bccc2), we hypothesize that geophysical models suffer from similar ex-post bias. We conduct a systematic audit of validation protocols in top-cited literature and re-evaluate baseline spatiotemporal models (ConvLSTM) under strict ex-ante (chronological) versus standard ex-post (random) validation regimes. Validation Plan: We compare Brier Scores and AUPRC across protocols. Pending Results: Experimental execution is pending; we anticipate a significant drop in skill scores under ex-ante conditions if the hypothesis holds.

## Methods
1. Literature Audit: Code validation methods in top-100 cited papers for temporal leakage. 2. Comparative Modeling: Train ConvLSTM models on IBTrACS/ERA5 data. Arm A (Ex-Post): Random temporal shuffling. Arm B (Ex-Ante): Strict chronological splitting (train on t<T, test on t>=T). 3. Statistical Analysis: Compare performance metrics to quantify bias magnitude.

## Experiments
### Baselines


```json
[
  "Persistence Model (climatology baseline)",
  "Standard ConvLSTM with Random Temporal Split (representing typical ex-post approach)",
  "Standard ConvLSTM with Strict Chronological Split (representing ex-ante approach)"
]
```


### Metrics


```json
[
  "Brier Score (probabilistic accuracy)",
  "Area Under Precision-Recall Curve (AUPRC) (critical for imbalanced extreme events)",
  "Top-K Recall (ability to rank highest-risk regions)",
  "Performance Delta (difference in skill scores between ex-post and ex-ante protocols)"
]
```


### Ablation
Vary the length of the training window to assess sensitivity to data volume. Remove ensemble-derived features to test if single-system observables show different bias patterns.

### Validation Protocol
Strict Time-Series Cross-Validation for the ex-ante arm: Training data is restricted to years [Y_start, Y_test-1]. Test data is year Y_test. No shuffling allowed. Hyperparameters are tuned on a validation set strictly preceding the test year. For the ex-post arm, standard k-fold cross-validation with random shuffling is used to simulate common retrospective fitting practices.

## Results
当前状态：待执行验证实验。系统已生成可复现实验脚本、数据字段清单与评价指标，尚未运行真实实验。

## References
- **EV-Q110-caa38ce124360ec0211bccc2** · arxiv · arXiv:1407.6333
  - authors: Not available · year: Not available
  - url: https://arxiv.org/pdf/1407.6333.pdf · doi: Not available
  - reliability_note: eligibility_status=FULLTEXT_VERIFIED; topic_relevance_status=DIRECT_QUESTION_CORE; locator=page:2|section:page-2|paragraph:1; content_sha256=6ebf1daad0357d657c35f2f07ee0c94eadd82bf680af47e53224969dcda88586

## Reviewer Comments
- The revised hypothesis correctly reframes the claim as a 'Cross-Domain Methodological Transfer Hypothesis', explicitly treating the lack of direct geophysical evidence as the object of study rather than ignoring it.
- Experimental design now includes a mandatory preliminary literature audit to validate domain transferability before proceeding to full meta-analysis, directly addressing the previous critical issue regarding unverified assumptions.
- The assertion of weather model overfitting has been successfully replaced with a testable question about protocol similarity, removing the unsubstantiated premise.
- Domain transferability is now explicitly listed as the primary risk and knowledge_gap in the hypothesis metadata.
- Results are correctly marked as pending; no fabrication detected.
- References are strictly limited to allowed EvidenceCards (EV-Q110-caa38ce124360ec0211bccc2); external datasets (IBTrACS, ERA5) are appropriately categorized as experimental resources rather than evidentiary support for the core claim.

## Revision History
- auto_revision_1: 依据评审意见重做假设与实验设计。

## Reproducibility Checklist
- Code repository with deterministic seeds for all model training runs
- Pre-processing scripts for IBTrACS and ERA5 data alignment
- Clear definition and code implementation of 'Ex-Post' vs 'Ex-Ante' data splitting logic
- Meta-analysis coding sheet with inter-rater reliability scores for literature classification
- Containerized environment (Docker) specifying all library versions

