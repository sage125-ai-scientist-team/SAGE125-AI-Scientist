# Constraining the AGN Origin of High-Energy Cosmic Neutrinos via Multi-Messenger Stacking Analysis and PSF Uncertainty Propagation

## Input Question
What is the origin of high-energy cosmic neutrinos?

## Domain
Astronomy

## Validation Status
needs_data

## Problem Statement
The IceCube Neutrino Observatory has detected extraterrestrial neutrinos in the TeV-PeV energy range, but their specific astrophysical sources remain unidentified. While Active Galactic Nuclei (AGN) and starburst galaxies are candidate sources, current evidence does not definitively establish which population dominates the flux or the precise acceleration mechanisms involved.

## Rationale
Identifying the sources of high-energy cosmic neutrinos is critical for understanding extreme particle acceleration in the universe and resolving the century-old mystery of ultrahigh-energy cosmic ray origins. The provided evidence confirms the detection of these neutrinos (EV-Q066-adc90af4a34fccc99300ab02, EV-Q066-e4f904ffe04f69fbe6d26c70) but highlights the need for next-generation sensitivity to pinpoint sources. This plan proposes a rigorous statistical test of the AGN hypothesis using existing multi-messenger data.

## Generated Hypotheses

### Hypothesis 1
- **Hypothesis**: High-energy cosmic neutrinos originate predominantly from hadronic interactions within Active Galactic Nuclei (AGN), implying a correlated diffuse gamma-ray flux consistent with Fermi-LAT constraints.
- **Mechanism**: Protons accelerated in AGN jets interact with ambient photons or matter via p-p or p-γ collisions, producing charged pions that decay into high-energy neutrinos and neutral pions that decay into gamma rays. If AGNs are the dominant source, the integrated neutrino flux must be accompanied by a predictable level of associated gamma-ray emission not exceeding Fermi-LAT limits.
- **Falsifiable Prediction**: Stacking analysis of known AGN positions using IceCube HESE data will yield a post-trial significance >3σ for neutrino excess, AND the implied gamma-ray flux derived from this neutrino signal will remain below the Fermi-LAT isotropic diffuse background upper limits. Failure to meet BOTH criteria simultaneously falsifies the hypothesis as the dominant origin mechanism.
- **Required Observations**: Spatial correlation statistics between IceCube high-energy neutrino arrival directions and catalogs of AGNs；Diffuse gamma-ray background measurements from Fermi-LAT to constrain hadronic vs. leptonic models；Spectral energy distribution modeling of candidate AGNs matching neutrino energy range
- **Risk of Being Wrong**: Current evidence confirms neutrino detection but does not establish source association; if no spatial correlation is found with improved statistics, or if gamma-ray constraints rule out sufficient hadronic power, this hypothesis is weakened.

### Hypothesis 2
- **Hypothesis**: Starburst galaxies contribute significantly to the high-energy neutrino flux through cosmic ray interactions with dense interstellar medium, distinct from AGN-dominated scenarios.
- **Mechanism**: Enhanced star formation rates in starburst galaxies lead to high supernova rates and cosmic ray acceleration; these cosmic rays interact with the dense gas, producing neutrinos via pion decay. This mechanism predicts a neutrino flux correlated with star formation rate density rather than AGN luminosity.
- **Falsifiable Prediction**: If starburst galaxies are major contributors, neutrino event rates should correlate with tracers of star formation (e.g., infrared luminosity) independent of AGN activity, and the spectral shape should reflect cosmic ray interaction timescales in dense media.
- **Required Observations**: Cross-correlation of neutrino events with starburst galaxy catalogs excluding AGN-host systems；Multi-wavelength characterization (IR, radio) of neutrino error regions；Comparison of neutrino spectral index with predictions from starburst cosmic ray propagation models
- **Risk of Being Wrong**: The provided evidence does not confirm starburst contributions; if correlations with star formation tracers remain insignificant after accounting for AGN contamination, this hypothesis lacks support.

### Hypothesis 3
- **Hypothesis**: The observed high-energy neutrino flux arises from a composite population where neither AGNs nor starburst galaxies individually dominate, requiring next-generation telescopes to resolve individual sources.
- **Mechanism**: Multiple source classes (AGNs, starbursts, GRBs, etc.) each contribute sub-dominant fractions to the total flux, such that current detector sensitivity cannot distinguish individual populations via stacking or correlation. Resolution requires improved angular resolution and effective area.
- **Falsifiable Prediction**: If this hypothesis is correct, current-generation stacking analyses will remain inconclusive (<3σ significance for any single class), but next-generation detectors will identify individual bright sources or achieve >5σ population discrimination within 5 years of operation.
- **Required Observations**: Null results from current stacking/correlation studies with existing IceCube data；Detection of point-like or population-resolved neutrino sources by next-generation observatories；Improved source catalog completeness at relevant redshifts
- **Risk of Being Wrong**: This hypothesis risks being unfalsifiable in the short term; however, it is weakened if current data already shows strong (>5σ) correlation with a specific source class, which would indicate a dominant population exists.

## Technical Details
This experiment tests the hypothesis that Active Galactic Nuclei (AGN) are the dominant source of high-energy cosmic neutrinos via hadronic interactions. The core mechanism posits that proton-photon (p-gamma) or proton-proton (p-p) collisions in AGN jets produce pions, which decay into neutrinos and gamma rays. Consequently, a spatial correlation between IceCube neutrino events and known AGN catalogs is expected, accompanied by a diffuse gamma-ray flux consistent with Fermi-LAT constraints. The study employs a likelihood-ratio stacking analysis to search for neutrino excesses at AGN positions. Crucially, systematic uncertainties in the IceCube point-spread function (PSF) are propagated into the likelihood ratio test statistic via marginalization over angular error parameters, ensuring the validity of the >3σ threshold. Both pre-trial and post-trial p-values are explicitly calculated to account for look-elsewhere effects across AGN subclasses and energy bins.

## Datasets
### Source


```json
[
  {
    "name": "IceCube High-Energy Starting Events (HESE)",
    "description": "Publicly available catalog of high-energy neutrino candidates detected by IceCube, including event energies, arrival directions, and estimated background probabilities.",
    "evidence_ids": [
      "EV-Q066-adc90af4a34fccc99300ab02",
      "EV-Q066-e4f904ffe04f69fbe6d26c70"
    ],
    "access_type": "public_release",
    "format": "FITS/CSV"
  },
  {
    "name": "AGN Catalogs (e.g., Fermi-LAT 4LAC or Veron-Cetty)",
    "description": "Comprehensive catalogs of Active Galactic Nuclei with known positions, redshifts, and multi-wavelength fluxes.",
    "evidence_ids": [
      "EV-Q066-adc90af4a34fccc99300ab02"
    ],
    "access_type": "public_archive",
    "format": "VOTable/CSV"
  }
]
```


### Target


```json
[
  {
    "name": "Fermi-LAT Diffuse Gamma-Ray Background Data",
    "description": "Measurements of the isotropic diffuse gamma-ray background used to constrain the total hadronic emission from the AGN population.",
    "evidence_ids": [
      "EV-Q066-adc90af4a34fccc99300ab02"
    ],
    "access_type": "public_archive",
    "format": "FITS"
  }
]
```


## Paper Abstract
Background: The IceCube Neutrino Observatory has detected high-energy extraterrestrial neutrinos, yet their astrophysical sources remain elusive. Active Galactic Nuclei (AGN) are leading candidates due to their potential for hadronic particle acceleration. Methods: We propose a rigorous likelihood-ratio stacking analysis correlating IceCube High-Energy Starting Events (HESE) with comprehensive AGN catalogs. To address systematic uncertainties, we propagate IceCube point-spread function (PSF) errors via marginalization in the likelihood function. We further constrain the hadronic model by comparing predicted gamma-ray fluxes against Fermi-LAT diffuse background measurements. Validation Plan: The hypothesis is falsified if no significant spatial correlation (>3σ post-trial) is found or if the associated gamma-ray flux exceeds observational limits. Results: pending. This study aims to provide statistically robust constraints on the AGN contribution to the cosmic neutrino flux using existing public data.

## Methods
1. **Data Preprocessing**: Filter IceCube HESE data for high-purity astrophysical candidates (E > 60 TeV) to minimize atmospheric background. Match neutrino arrival directions with AGN coordinates within angular error radii defined by IceCube's point-spread function (PSF). 
2. **PSF Uncertainty Propagation**: Incorporate systematic uncertainties in the IceCube PSF by marginalizing the likelihood function over the angular error parameters for each event, rather than using fixed error circles. This ensures robust significance estimation.
3. **Stacking Analysis**: Perform a maximum-likelihood ratio test to evaluate the significance of neutrino clustering around AGN positions compared to an isotropic background model. The test statistic accounts for individual event weights based on energy and angular uncertainty. 
4. **Statistical Correction**: Explicitly calculate both pre-trial p-values (for specific AGN subsets) and post-trial p-values (corrected for multiple trials across different AGN subclasses, energy ranges, and spatial windows) to address look-elsewhere effects.
5. **Multi-messenger Consistency Check**: For any significant correlation found, calculate the expected gamma-ray flux using standard hadronic interaction models (p-p or p-gamma). Compare this predicted flux against the Fermi-LAT diffuse background measurements and individual source limits to verify physical consistency.

## Experiments
### Baselines


```json
[
  "Isotropic Background Model: Assumes neutrinos arrive uniformly from all directions, representing the null hypothesis of no source association.",
  "Galactic Plane Correlation Model: Tests if neutrinos correlate with the Milky Way's galactic plane rather than extragalactic AGNs, serving as a control for local astrophysical backgrounds."
]
```


### Metrics


```json
[
  "Log-Likelihood Ratio Test Statistic (TS): Quantifies the preference for the AGN-correlated model over the isotropic background.",
  "Pre-trial and Post-trial Significance (sigma): Statistical significance of the excess, corrected for multiple trials across different AGN subclasses or energy ranges.",
  "Gamma-ray Flux Upper Limits: Constraints on the hadronic gamma-ray component derived from the neutrino flux, compared against Fermi-LAT observations."
]
```


### Ablation


```json
[
  "Exclude Blazars: Remove blazar-type AGNs from the catalog to test if the correlation is driven specifically by this subclass.",
  "Energy Threshold Variation: Vary the minimum neutrino energy threshold (e.g., 30 TeV vs 100 TeV) to assess spectral dependence of the correlation."
]
```


### Validation Protocol
Split the IceCube dataset into temporal halves (e.g., first 5 years vs. next 5 years) to perform a cross-validation. A significant signal in the discovery sample must be confirmed in the independent validation sample to claim robustness. Additionally, perform Monte Carlo simulations of isotropic neutrino skies to estimate the false-positive rate of the stacking method and validate the post-trial correction procedure.

## Results
当前状态：待执行验证实验。系统已生成可复现实验脚本、数据字段清单与评价指标，尚未运行真实实验。

## References
- **EV-Q066-adc90af4a34fccc99300ab02** · arxiv · arXiv:1407.2536
  - authors: Not available · year: Not available
  - url: https://arxiv.org/pdf/1407.2536.pdf · doi: Not available
  - reliability_note: eligibility_status=FULLTEXT_VERIFIED; topic_relevance_status=DIRECT_QUESTION_CORE; locator=page:1|section:page-1|paragraph:1; content_sha256=0bb80c2695fc28bbe4be830b6fea476516896596c41e4641459832fea5ea77b6
- **EV-Q066-e4f904ffe04f69fbe6d26c70** · arxiv · arXiv:1409.2589
  - authors: Not available · year: Not available
  - url: https://arxiv.org/pdf/1409.2589.pdf · doi: Not available
  - reliability_note: eligibility_status=FULLTEXT_VERIFIED; topic_relevance_status=DIRECT_QUESTION_CORE; locator=page:4|section:page-4|paragraph:1; content_sha256=d1829ceaf14d3a88c61e60fda757bc96e37fce7b2d07fef7594ab78ed3b11055

## Reviewer Comments
- The revision successfully addresses the previous critical issues regarding statistical rigor. The methods section now explicitly includes Step 4 for calculating both pre-trial and post-trial p-values to account for look-elsewhere effects, closing issue required_revision:dbfe3bb2f524.
- The methods section has been updated with Step 2 describing PSF uncertainty propagation via marginalization over angular error parameters, directly addressing the concern about >3σ threshold validity (closing issue required_revision:1904c89fe4cf).
- Evidence grounding remains robust, with all factual claims traceable to EV-Q066-adc90af4a34fccc99300ab02 and EV-Q066-e4f904ffe04f69fbe6d26c70. No unauthorized evidence IDs were introduced.
- The Results field correctly maintains 'pending' status, confirming no fabrication of experimental outcomes occurred during the revision process.
- Reproducibility checklist has been updated to include specific requirements for publishing Monte Carlo simulation scripts and PSF marginalization code, enhancing verification potential.

## Revision History
- auto_revision_1: 依据评审意见重做假设与实验设计。

## Reproducibility Checklist
- Use publicly available IceCube HESE data releases as cited in EV-Q066-adc90af4a34fccc99300ab02.
- Document exact AGN catalog version and selection criteria (e.g., flux limits, redshift range).
- Provide code for the likelihood-ratio stacking analysis with PSF uncertainty marginalization.
- Explicitly report both pre-trial and post-trial p-values to account for look-elsewhere effects.
- Include detailed assumptions for the hadronic interaction models used in gamma-ray flux prediction.
- Publish Monte Carlo simulation scripts used for background estimation and significance calibration.

