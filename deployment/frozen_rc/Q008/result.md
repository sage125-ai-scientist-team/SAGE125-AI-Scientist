# Observational Limitations of the LIFE Mission in Detecting Molecular Homochirality: A Textual Audit of Instrument Specifications

## Input Question
Why does life require chirality?

## Domain
Chemistry

## Validation Status
needs_data

## Problem Statement
The user asks for the biochemical mechanism explaining why life requires molecular chirality (homochirality). However, the provided evidence set (EV-Q008-*) consists exclusively of technical papers regarding the design and retrieval capabilities of the LIFE (Large Interferometer For Exoplanets) mission, focusing on intensity-based spectroscopy for atmospheric biosignatures. There is a fundamental domain mismatch between the biochemical question and the astronomical instrumentation evidence.

## Rationale
Since no allowed evidence card contains information on stereochemistry, enzyme kinetics, or molecular biology, it is impossible to answer the 'why' of biological chirality using the provided sources. Instead, this research plan investigates the observational constraints: it tests the hypothesis that the current LIFE mission architecture, as described in the evidence, lacks the polarimetric capabilities necessary to detect homochirality remotely. This reframes the inquiry into a verifiable audit of instrument specifications within the allowed evidence set.

## Generated Hypotheses

### Hypothesis 1
- **Hypothesis**: Current LIFE mission architectures, as defined in the provided evidence set, lack the polarimetric measurement capabilities required to detect homochirality, rendering the biochemical necessity of chirality observationally unverifiable with this specific instrument baseline.
- **Mechanism**: The detection of molecular homochirality via remote sensing physically requires circular polarization measurements (circular dichroism or optical rotatory dispersion). The provided evidence cards (EV-Q008-e23b1ea12259b0e264bc2da2, EV-Q008-e173ebb45997fa7670a0deb2) define the LIFE mission's wavelength coverage, spectral resolution, and sensitivity requirements exclusively for intensity-based spectroscopy of atmospheric gases (e.g., O3, CH4). Since the instrument specifications do not include polarimetric channels or modulation optics, the physical observable necessary to validate chirality is absent from the system design.
- **Falsifiable Prediction**: A systematic audit of the instrument parameters and retrieval frameworks described in EV-Q008-e23b1ea12259b0e264bc2da2 and EV-Q008-e173ebb45997fa7670a0deb2 will confirm zero references to Stokes V parameters, circular polarization, or chiral-specific spectral features. If any such capability is documented, the hypothesis is falsified.
- **Required Observations**: Complete list of instrumental observables and detector modes specified in EV-Q008-e23b1ea12259b0e264bc2da2；Atmospheric retrieval parameter lists and forward model physics from EV-Q008-f28910b2f0fe1504e61fd9da and EV-Q008-e173ebb45997fa7670a0deb2；Verification of absence of polarimetric calibration sources or modulators in the proposed Emma X-array or kernel-nulling designs
- **Risk of Being Wrong**: The hypothesis assumes the provided evidence cards are exhaustive regarding the current LIFE baseline. If supplementary technical documentation (not in the allowed set) includes polarimetry, or if 'kernel-nulling' inherently enables polarization separation without explicit mention in these texts, the claim of incapability would be incorrect based on external knowledge, though valid within the closed evidence set.

### Hypothesis 2
- **Hypothesis**: The question 'Why does life require chirality?' cannot be addressed using the current LIFE evidence bundle because the available data constrains only atmospheric composition retrieval, creating a fundamental domain mismatch between the biochemical query and the astronomical evidence.
- **Mechanism**: The provided evidence cards focus entirely on exoplanet characterization metrics (SNR, spectral resolution, architecture optimization) for detecting gaseous biosignatures. There is no causal or correlational link established in these texts between atmospheric spectral features and the molecular stereochemistry of surface life. Therefore, any attempt to derive the 'reason' for chirality from this dataset is structurally invalid, regardless of the biochemical truth.
- **Falsifiable Prediction**: Semantic analysis of all four allowed evidence IDs will yield no mentions of 'stereochemistry', 'enantiomer', 'chirality', 'homochirality', or 'handedness'. If any of these terms appear in a functional context (not just as a keyword in a bibliography), the hypothesis of total domain mismatch is weakened.
- **Required Observations**: Full-text search results for chirality-related terminology across EV-Q008-e23b1ea12259b0e264bc2da2, EV-Q008-f28910b2f0fe1504e61fd9da, EV-Q008-b9756de0118da590def87983, EV-Q008-e173ebb45997fa7670a0deb2；Mapping of retrieved atmospheric parameters to biological mechanisms in the cited retrieval frameworks
- **Risk of Being Wrong**: Low risk within the closed system. The primary risk is that implicit assumptions in the retrieval papers (e.g., assuming Earth-like biology implies chirality) might be interpreted as addressing the 'why', but strictly speaking, they do not explain the requirement.

## Technical Details
This experiment is a systematic audit of the technical specifications and retrieval frameworks defined in the allowed evidence set to verify the absence of polarimetric capabilities. The hypothesis posits that the LIFE mission architecture, as described in EV-Q008-e23b1ea12259b0e264bc2da2 and EV-Q008-e173ebb45997fa7670a0deb2, is designed exclusively for intensity-based spectroscopy (Stokes I) and lacks the optical components (e.g., modulators, polarizers) or data processing pipelines required to measure circular polarization (Stokes V), which is the physical observable necessary for detecting molecular homochirality. The experiment involves parsing the full text of the specified evidence cards for keywords related to polarization, chirality, and Stokes parameters. It also involves mapping the listed instrument requirements (wavelength coverage, spectral resolution, sensitivity) against the known physical requirements for chiral discrimination to confirm the domain mismatch. No synthetic spectral simulation of chiral molecules is performed, as the primary test is the verification of instrument design limitations documented in the source texts.

## Datasets
### Source


```json
[
  {
    "id": "EV-Q008-e23b1ea12259b0e264bc2da2",
    "type": "text",
    "description": "Technical paper describing LIFE mission architectures (Emma X-array vs. kernel-nulling), focusing on interferometric baseline, collecting area, and achromatic phase shifts."
  },
  {
    "id": "EV-Q008-e173ebb45997fa7670a0deb2",
    "type": "text",
    "description": "Paper deriving LIFE science requirements including wavelength coverage, spectral resolution, and sensitivity for atmospheric characterization of terrestrial exoplanets."
  },
  {
    "id": "EV-Q008-f28910b2f0fe1504e61fd9da",
    "type": "text",
    "description": "Study on atmospheric retrieval performance for biosignatures (O3, CH4) using LIFE-like instrument models."
  }
]
```


### Target
Structured inventory of instrumental observables, detection methods, and retrieval parameters explicitly mentioned in the source texts.

## Paper Abstract
Background: The question of why life requires chirality is fundamental to biochemistry, yet remote detection of homochirality requires specific polarimetric capabilities. Methods: We conducted a systematic textual audit of four key evidence cards (EV-Q008-*) describing the Large Interferometer For Exoplanets (LIFE) mission architecture and retrieval frameworks. We searched for mentions of polarimetry, circular dichroism, and chiral discrimination mechanisms. Validation Plan: We verify whether the stated instrument requirements (wavelength, resolution, sensitivity) and retrieval parameters include Stokes V measurements or chiral-specific observables. Results: pending (待执行验证实验).

## Methods
1. Text Mining & Keyword Search: Systematically search the full text of EV-Q008-e23b1ea12259b0e264bc2da2, EV-Q008-e173ebb45997fa7670a0deb2, and EV-Q008-f28910b2f0fe1504e61fd9da for terms: 'polarization', 'circular', 'Stokes', 'chiral', 'enantiomer'. 2. Instrument Specification Audit: Extract all listed detector modes and optical elements to verify if any component supports polarization analysis. 3. Retrieval Framework Analysis: Examine forward models in EV-Q008-f28910b2f0fe1504e61fd9da to confirm they are limited to scalar intensity spectra.

## Experiments
### Baselines


```json
[
  "Null Baseline: Assume no polarimetric capability exists unless explicitly stated in the text.",
  "General Biosignature Baseline: Compare the listed capabilities against standard intensity-based biosignature detection (O3, CH4, H2O) to confirm the instrument is optimized for these, not chirality."
]
```


### Metrics


```json
[
  "Keyword Presence Count: Number of occurrences of polarization/chirality-related terms in the allowed evidence texts.",
  "Instrument Observable Completeness: Binary flag (0/1) indicating whether Stokes V or circular polarization is listed as a measurable quantity.",
  "Retrieval Parameter Scope: List of retrieved atmospheric parameters to verify exclusion of chiral metrics."
]
```


### Ablation
N/A (Textual audit does not involve parameter ablation in the traditional sense; instead, we verify consistency across all three provided evidence cards).

### Validation Protocol
Double-blind keyword search by two independent agents to ensure no mentions of polarimetry are missed. Cross-verification of instrument specs against the abstract and conclusion sections of each paper to ensure no hidden capabilities are described in supplementary contexts within the provided texts.

## Results
当前状态：待执行验证实验。系统已生成可复现实验脚本、数据字段清单与评价指标，尚未运行真实实验。

## References
- **EV-Q008-e23b1ea12259b0e264bc2da2** · arxiv · arXiv:2201.04891
  - authors: Not available · year: Not available
  - url: https://arxiv.org/pdf/2201.04891.pdf · doi: Not available
  - reliability_note: eligibility_status=FULLTEXT_VERIFIED; topic_relevance_status=DIRECT_QUESTION_CORE; locator=page:1|section:page-1|paragraph:1; content_sha256=d7a7cc4d188ba4b341cd046d59919341c90acf61f96d4a1a4f35c7e416414a4d
- **EV-Q008-f28910b2f0fe1504e61fd9da** · arxiv · arXiv:2406.13037
  - authors: Not available · year: Not available
  - url: https://arxiv.org/pdf/2406.13037.pdf · doi: Not available
  - reliability_note: eligibility_status=FULLTEXT_VERIFIED; topic_relevance_status=DIRECT_QUESTION_CORE; locator=page:2|section:page-2|paragraph:1; content_sha256=3a57405758b1fa7123f159348d90fdda14772aba7ecf8c8c2054061c0f5dcfac
- **EV-Q008-b9756de0118da590def87983** · arxiv · arXiv:2204.10041
  - authors: Not available · year: Not available
  - url: https://arxiv.org/pdf/2204.10041.pdf · doi: Not available
  - reliability_note: eligibility_status=FULLTEXT_VERIFIED; topic_relevance_status=DIRECT_QUESTION_CORE; locator=page:1|section:page-1|paragraph:1; content_sha256=6477fdf72f4f2447e2b88bcd3312e9ca07f1177482338c7dd9f8ec73b976166a
- **EV-Q008-e173ebb45997fa7670a0deb2** · arxiv · arXiv:2303.04727
  - authors: Not available · year: Not available
  - url: https://arxiv.org/pdf/2303.04727.pdf · doi: Not available
  - reliability_note: eligibility_status=FULLTEXT_VERIFIED; topic_relevance_status=DIRECT_QUESTION_CORE; locator=page:2|section:page-2|paragraph:1; content_sha256=e993009ca312577865ff29a88d77eeeb6bffb96496b4408dc45445ec0b3fb055

## Reviewer Comments
- The revised hypothesis correctly reframes the inquiry from an unsupported biochemical assertion to a verifiable audit of instrument capabilities within the allowed evidence set.
- All references to 'lock-and-key' mechanisms and intensity-based chiral retrieval have been removed, resolving the critical scientific soundness issues identified in the previous review.
- The experiment design is now a valid textual audit of EV-Q008-* evidence cards for polarimetric keywords, which is fully reproducible and grounded strictly in the provided sources.
- The Results field correctly indicates 'pending' status, avoiding any fabrication of experimental outcomes.
- Knowledge gaps regarding the biochemical necessity of chirality are explicitly acknowledged in the EvidenceExtractionResult rather than being asserted as facts.

## Revision History
- auto_revision_1: 依据评审意见重做假设与实验设计。

## Reproducibility Checklist
- Use exact PDF/text versions of EV-Q008-e23b1ea12259b0e264bc2da2, EV-Q008-e173ebb45997fa7670a0deb2, and EV-Q008-f28910b2f0fe1504e61fd9da as provided in the evidence catalog.
- Record all search terms and their context windows.
- Document the extraction logic for instrument specifications (e.g., tables vs. prose).
- Ensure no external knowledge about LIFE mission updates beyond the provided evidence IDs is introduced.

