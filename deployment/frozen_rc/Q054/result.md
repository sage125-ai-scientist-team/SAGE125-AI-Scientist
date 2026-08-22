# Constraining the Galactic Origin of High-Energy Cosmic Rays via Multi-Messenger Limits from Fermi-LAT and IceCube

## Input Question
What is the origin of cosmic rays?

## Domain
Astronomy

## Validation Status
needs_data

## Problem Statement
The origin of high-energy cosmic rays remains a fundamental question in astrophysics. While lower-energy cosmic rays are generally accepted to originate from Galactic sources like supernova remnants, the sources of the highest-energy particles and those associated with high-energy neutrinos detected by IceCube are less certain. Specifically, it is unclear whether these high-energy components originate from Galactic accelerators or extragalactic sources, given the constraints imposed by multi-messenger observations.

## Rationale
Understanding the origin of cosmic rays is crucial for modeling high-energy astrophysical processes. Evidence suggests that Galactic origins may be insufficient to explain the observed flux of high-energy neutrinos detected by IceCube, as such origins would produce accompanying gamma-ray emissions that exceed limits set by Fermi-LAT observations. This implies a significant extragalactic component for at least the highest-energy cosmic rays.

## Generated Hypotheses

### Hypothesis 1
- **Hypothesis**: The high-energy cosmic rays associated with IceCube neutrinos originate predominantly from extragalactic sources, as Galactic accelerators are insufficient to produce the observed neutrino flux given Fermi-LAT gamma-ray constraints and standard propagation models.
- **Mechanism**: Cosmic ray protons accelerated in extragalactic environments interact via pp or pγ processes to produce pions that decay into neutrinos; if Galactic sources were dominant, the accompanying gamma-ray emission from neutral pion decay would exceed Fermi-LAT upper limits on diffuse Galactic emission when modeled with specific GALPROP/DRAGON configurations and >100 TeV cross-section uncertainties.
- **Falsifiable Prediction**: If Galactic sources contribute >50% of the IceCube neutrino flux above 100 TeV, then the corresponding diffuse Galactic gamma-ray flux at GeV-TeV energies must be detectable by Fermi-LAT and consistent with specific GALPROP/DRAGON configuration files (e.g., halo size, diffusion coefficients) after propagating systematic uncertainties in pp/pγ interaction cross-sections at >100 TeV.
- **Required Observations**: Precise measurement of diffuse Galactic gamma-ray intensity and spectrum using Fermi-LAT public data；IceCube neutrino flux spectrum and sky map above 100 TeV；Modeling of pp/pγ interaction yields linking neutrino and gamma-ray fluxes with explicit treatment of >100 TeV cross-section systematics；Specific GALPROP/DRAGON configuration files defining halo size and diffusion coefficients
- **Risk of Being Wrong**: If improved modeling of Galactic CR propagation (e.g., different halo sizes) or updated >100 TeV cross-sections reveals a hidden Galactic gamma-ray component consistent with IceCube flux within systematic uncertainties, the extragalactic dominance hypothesis would be weakened.

### Hypothesis 2
- **Hypothesis**: A distinct population of transient extragalactic accelerators produces both the high-energy cosmic rays and the IceCube neutrinos, with time-correlated multi-messenger signals, implying that the diffuse flux constraint alone is insufficient to identify specific source classes.
- **Mechanism**: Relativistic jets in transient extragalactic sources accelerate protons to ultra-high energies; these protons interact with ambient photons or matter to produce neutrinos and gamma-rays simultaneously, leading to temporal and directional correlations between neutrino events and electromagnetic transients.
- **Falsifiable Prediction**: If such transients are the dominant source, then stacking analyses of IceCube neutrino arrival times and directions with known blazar/GRB catalogs should reveal statistically significant correlations beyond background expectations; absence of such correlations would weaken this specific source-class hypothesis but not the general extragalactic origin.
- **Required Observations**: Time-resolved IceCube neutrino event list with directional reconstruction；Multi-wavelength monitoring data of candidate extragalactic transients；Cross-correlation statistical analysis between neutrino and EM datasets
- **Risk of Being Wrong**: Absence of significant neutrino-transient correlations in current or near-future datasets would challenge this hypothesis, though it could persist if sources are too faint or numerous to resolve individually.

## Technical Details
This experiment tests the hypothesis that IceCube's high-energy neutrino flux (>100 TeV) is predominantly extragalactic by leveraging the photon-neutrino connection in hadronic interactions (pp and pγ). The core mechanism relies on the fact that neutral pion decay produces gamma-rays, while charged pion decay produces neutrinos. If Galactic cosmic ray accelerators were responsible for the observed IceCube flux, the associated diffuse Galactic gamma-ray emission would exceed the upper limits established by Fermi-LAT observations. The study involves reconstructing the expected diffuse Galactic gamma-ray spectrum from a hypothetical Galactic neutrino component and comparing it against actual Fermi-LAT data. We will use public datasets from both observatories, applying specific GALPROP/DRAGON configuration files to link the two messengers, and explicitly propagate systematic uncertainties in >100 TeV cross-sections.

## Datasets
### Source


```json
[
  {
    "name": "Fermi-LAT Public Data Release",
    "description": "Gamma-ray intensity maps and spectral data for the Milky Way, specifically focusing on the diffuse Galactic emission components.",
    "access_url": null,
    "evidence_ids": [
      "EV-Q054-3f18f925ab28e65ee5288c00"
    ]
  },
  {
    "name": "IceCube High-Energy Starting Events (HESE) or Throughgoing Muons Dataset",
    "description": "Neutrino event lists and flux measurements above 100 TeV, including sky maps to separate Galactic plane contributions from isotropic background.",
    "access_url": null,
    "evidence_ids": [
      "EV-Q054-3f18f925ab28e65ee5288c00"
    ]
  }
]
```


### Target


```json
{
  "name": "Constrained Galactic Neutrino Flux Model",
  "description": "A derived upper limit on the Galactic contribution to the IceCube neutrino flux, consistent with Fermi-LAT gamma-ray constraints. This target explicitly references specific GALPROP/DRAGON configuration files (e.g., halo size 4-10 kpc, diffusion coefficient D0 ~ 10^28 cm^2/s) to define the propagation model parameters."
}
```


## Paper Abstract
Background: The origin of high-energy cosmic rays is debated, with multi-messenger astronomy offering new constraints. Method: We test the hypothesis that high-energy cosmic rays associated with IceCube neutrinos are predominantly extragalactic. By modeling the photon-neutrino connection in pp and pγ interactions, we calculate the expected diffuse Galactic gamma-ray emission if Galactic sources dominated the IceCube flux. We use specific GALPROP/DRAGON configurations and propagate systematic uncertainties in >100 TeV cross-sections. Validation Plan: Compare modeled gamma-ray fluxes against Fermi-LAT observations to derive upper limits on the Galactic contribution. Results: pending (待执行验证实验).

## Methods
1. Data Preprocessing: Extract diffuse Galactic gamma-ray spectrum from Fermi-LAT data and neutrino flux from IceCube HESE dataset (>100 TeV). 2. Modeling: Use hadronic interaction models to link neutrino and gamma-ray production. Simulate expected gamma-ray output for varying Galactic fractions (50-100%) using GALPROP/DRAGON. 3. Uncertainty Propagation: Vary pp/pγ cross-section models (SIBYLL, QGSJET, EPOS) to account for systematics. 4. Statistical Comparison: Calculate chi-squared statistics to test consistency with Fermi-LAT limits.

## Experiments
### Baselines


```json
[
  "Purely Extragalactic Model: Assumes 0% Galactic contribution; checks consistency with isotropic neutrino background.",
  "Maximal Galactic Model: Assumes 100% of IceCube flux is Galactic; tests if this violates Fermi-LAT constraints.",
  "Standard CR Propagation Model: Uses accepted Galactic CR density distributions to predict baseline gamma-ray emission without new neutrino sources."
]
```


### Metrics


```json
[
  "Chi-squared goodness-of-fit between modeled and observed Fermi-LAT gamma-ray spectra.",
  "Upper limit on Galactic fraction of IceCube flux at 95% confidence level.",
  "Bayesian Evidence Ratio comparing Extragalactic-dominant vs. Galactic-dominant hypotheses."
]
```


### Ablation
Vary the assumed proton-proton (pp) vs. proton-photon (pγ) interaction dominance in the source environment to see how it affects the gamma-ray/neutrino ratio. Test different Galactic CR halo sizes in propagation models.

### Validation Protocol
Cross-validate results using independent Fermi-LAT data releases (e.g., Pass 8 vs. earlier versions) and different IceCube event selections (HESE vs. throughgoing muons) to ensure systematic errors do not drive the conclusion.

## Results
当前状态：待执行验证实验。系统已生成可复现实验脚本、数据字段清单与评价指标，尚未运行真实实验。

## References
- **EV-Q054-3f18f925ab28e65ee5288c00** · arxiv · arXiv:1407.2536
  - authors: Not available · year: Not available
  - url: https://arxiv.org/pdf/1407.2536.pdf · doi: Not available
  - reliability_note: eligibility_status=FULLTEXT_VERIFIED; topic_relevance_status=DIRECT_QUESTION_CORE; locator=page:1|section:page-1|paragraph:1; content_sha256=0bb80c2695fc28bbe4be830b6fea476516896596c41e4641459832fea5ea77b6

## Reviewer Comments
- The revision successfully addresses the previous required revisions by explicitly specifying GALPROP/DRAGON configuration parameters (halo size 4-10 kpc, D0 ~ 10^28 cm^2/s) in the target dataset description.
- Method section now correctly details the propagation of systematic uncertainties for >100 TeV pp/pγ cross-sections using specific interaction models (SIBYLL, QGSJET, EPOS), resolving the prior model dependence concern.
- Hypothesis remains strictly grounded in EV-Q054-3f18f925ab28e65ee5288c00 without overclaiming causality or introducing unsupported evidence.
- Results field is correctly maintained as pending/not executed, ensuring no fabrication of experimental outcomes.
- Reproducibility checklist has been updated to include archiving of specific configuration files and uncertainty propagation methods, satisfying reproducibility standards.

## Revision History
- auto_revision_1: 依据评审意见重做假设与实验设计。

## Reproducibility Checklist
- Use publicly available Fermi-LAT and IceCube data repositories.
- Provide code for hadronic interaction yield calculations (e.g., using SOPHIA or similar libraries).
- Document all CR propagation parameters used in GALPROP/DRAGON simulations, specifically referencing the configuration files for halo size and diffusion coefficients.
- Archive analysis scripts and configuration files in a version-controlled repository.
- Explicitly document the method for propagating systematic uncertainties in >100 TeV cross-sections into the final upper limit.

