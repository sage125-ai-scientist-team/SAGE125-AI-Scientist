# Testing the Geometric Nature of Gravity: Constraining Post-Newtonian Parameters with GRAVITY Observations of SgrA* Amidst Extended Mass Degeneracies

## Input Question
What is gravity?

## Domain
Astronomy

## Validation Status
needs_data

## Problem Statement
Gravity is identified as one of the four fundamental interactions, yet its fundamental makeup remains a mystery. While Newton described it as attraction and Einstein's General Relativity (GR) as the bending of space-time, the underlying mechanism unifying these descriptions or revealing its quantum nature is unknown. Current observational capabilities, such as the GRAVITY instrument, allow for precision tests in strong-field regimes (e.g., near SgrA*), but distinguishing pure geometric effects from extended mass distributions (stellar cusp vs. dark matter spike) and instrumental systematics remains a critical challenge.

## Rationale
Understanding the nature of gravity requires testing its predictions in extreme environments where deviations from Newtonian physics are pronounced. The GRAVITY instrument provides unique data on stellar orbits near the Galactic Center's supermassive black hole. By rigorously modeling these orbits while accounting for degeneracies with extended mass distributions and instrumental systematics, we can validate whether gravity behaves strictly as a geometric curvature of spacetime (GR) or exhibits anomalies suggestive of new physics.

## Generated Hypotheses

### Hypothesis 1
- **Hypothesis**: Gravity is fundamentally a geometric curvature of spacetime as described by General Relativity, and its apparent 'mysterious makeup' arises solely from the lack of quantum unification rather than a failure of the geometric description at astrophysical scales accessible to current interferometry.
- **Mechanism**: Mass-energy dictates spacetime geometry; test particles follow geodesics in this curved manifold. In the weak-field limit, this geometry reduces to Newtonian potential (EV-Q067-4dc4b7d0e3d42b5dfdd38565). Deviations from Newtonian predictions in strong fields (e.g., near SgrA*) are strictly determined by the metric tensor without additional degrees of freedom. Any observed anomalies must be attributable to extended mass distributions (stellar cusp or dark matter spike) or instrumental systematics in K-band visibility data before invoking non-geometric physics.
- **Falsifiable Prediction**: High-precision measurements of stellar orbits near SgrA* using the GRAVITY instrument will match General Relativity's post-Newtonian parameters (specifically gravitational redshift and Schwarzschild precession) within observational error bars, showing no statistically significant residuals indicative of non-geometric forces or modified gravity after marginalizing over specific extended mass models and validated instrumental systematics.
- **Required Observations**: Spectroscopic radial velocity and astrometric position data of S-stars orbiting SgrA* obtained via GRAVITY instrument (EV-Q067-6b5243bd87caa32ed2094f3a)；K-band continuum flux and normalized visibility amplitude data from GRAVITY Unit Telescopes for precise orbit fitting and systematic error characterization (EV-Q067-da43d6b6c21ff8d094c67551)；Injection-recovery test results distinguishing instrumental systematics from physical signals in K-band visibility data
- **Risk of Being Wrong**: If GRAVITY data reveals systematic deviations from GR predictions (e.g., anomalous redshift or precession) that persist after accounting for specific extended mass models (stellar cusp vs. dark matter spike) and validated instrumental systematics, the pure geometric hypothesis would be weakened in favor of modified gravity or extra-dimensional theories.

### Hypothesis 2
- **Hypothesis**: The 'mysterious makeup' of gravity implies it is an emergent phenomenon or effective field theory that deviates from pure General Relativity at the strong-field regime accessible to current interferometry, manifesting as measurable anomalies in orbital dynamics near SgrA* distinct from extended mass effects.
- **Mechanism**: While recovering Newtonian gravity in the weak limit (EV-Q067-4dc4b7d0e3d42b5dfdd38565), the underlying microstructure of gravity introduces correction terms to the metric or adds scalar/vector fields that become non-negligible at high curvatures (near event horizons). These corrections alter the relationship between mass and spacetime curvature compared to standard GR, producing signatures distinguishable from stellar cusp or dark matter spike mass distributions.
- **Falsifiable Prediction**: Analysis of GRAVITY observations of SgrA* stellar orbits will detect statistically significant residuals (>3σ) from General Relativity predictions in gravitational redshift or orbital precession that correlate with proximity to the central mass and cannot be explained by specific extended mass models (stellar cusp vs. dark matter spike) or instrumental systematics validated through injection-recovery tests.
- **Required Observations**: Time-series astrometry and spectroscopy of S-stars at pericenter passage using GRAVITY (EV-Q067-6b5243bd87caa32ed2094f3a)；Comparative analysis of K-band visibility amplitudes to rule out instrumental artifacts via injection-recovery tests (EV-Q067-da43d6b6c21ff8d094c67551)；Bayesian model comparison between modified gravity and specific extended mass distribution models
- **Risk of Being Wrong**: If all strong-field observations remain consistent with GR within error margins, or if apparent anomalies are fully explained by conventional astrophysics (e.g., stellar cusp or dark matter spike) or instrumental systematics, the hypothesis of emergent/modified gravity at this scale is falsified.

### Hypothesis 3
- **Hypothesis**: Current observational constraints on gravity's nature are limited by the precision of interferometric baselines and degeneracy with extended mass models; next-generation analysis of existing GRAVITY K-band data can tighten bounds on post-Newtonian parameters by explicitly modeling stellar cusp vs. dark matter spike distributions and validating instrumental systematics.
- **Mechanism**: Systematic errors in previous GRAVITY analyses and degeneracy with unspecified extended mass distributions may have masked subtle signals. Re-processing raw flux and visibility data with improved calibration, explicit mass model comparison (stellar cusp vs. dark matter spike), and injection-recovery validation for K-band systematics will reduce uncertainty in orbital parameter estimation, enabling stricter tests of the Newtonian limit and relativistic corrections.
- **Falsifiable Prediction**: Re-analysis of archived GRAVITY Unit Telescope data with explicit extended mass modeling and instrumental systematic validation will yield reduced confidence intervals for post-Newtonian parameters that either confirm GR with higher precision or reveal previously hidden tensions with theoretical predictions, resolving degeneracy between mass distribution and PN parameters.
- **Required Observations**: Raw K-band continuum flux and normalized visibility amplitude data from GRAVITY UT baselines (EV-Q067-da43d6b6c21ff8d094c67551)；Calibration frames and transfer function data for systematic error characterization；Injection-recovery test results validating distinction between instrumental systematics and physical deviations
- **Risk of Being Wrong**: If re-analysis does not significantly improve parameter constraints due to fundamental noise limits, irreducible systematics, or persistent degeneracy between mass models and PN parameters despite explicit modeling, the hypothesis that better analysis can resolve gravity's makeup is operationally falsified for this dataset.

## Technical Details
This experiment tests the hypothesis that gravity is purely geometric (General Relativity) by analyzing high-precision astrometric and spectroscopic data of S-stars orbiting SgrA*. The core technical challenge is fitting orbital parameters while simultaneously solving for post-Newtonian (PN) corrections, specifically the gravitational redshift ($z_{GR}$) and Schwarzschild precession ($\Delta \omega$). We will employ a Bayesian inference framework using Markov Chain Monte Carlo (MCMC) methods to estimate the posterior distributions of PN parameters. The model will include standard Keplerian elements plus relativistic perturbations derived from the Schwarzschild metric. To address degeneracy, we explicitly model extended mass distributions using two distinct profiles: a stellar cusp (power-law density profile) and a dark matter spike (adiabatically contracted halo profile), marginalizing over their normalization and slope parameters. Systematic errors from instrumental calibration in K-band visibility data are characterized via transfer function modeling.

## Datasets
### Source


```json
[
  {
    "name": "GRAVITY SgrA* Spectroscopic and Astrometric Data",
    "description": "Time-series radial velocity and sky-position coordinates of S-stars (e.g., S2, S38) obtained via the GRAVITY instrument on the VLT Interferometer.",
    "evidence_ids": [
      "EV-Q067-6b5243bd87caa32ed2094f3a"
    ],
    "access_status": "public_candidate",
    "is_downloaded": false
  },
  {
    "name": "GRAVITY K-band Continuum and Visibility Data",
    "description": "Raw flux and normalized visibility amplitude data from the four Unit Telescopes and six baselines, used for precise astrometric centroiding and systematic error characterization.",
    "evidence_ids": [
      "EV-Q067-da43d6b6c21ff8d094c67551"
    ],
    "access_status": "public_candidate",
    "is_downloaded": false
  }
]
```


### Target


```json
{
  "parameter_estimates": "Posterior distributions for Post-Newtonian parameters (f_redshift, f_precession), extended mass model parameters (cusp slope/spike density), and orbital elements.",
  "residual_analysis": "Time-series residuals of astrometric position and radial velocity after subtracting the best-fit GR + Extended Mass model."
}
```


## Paper Abstract
Gravity remains the most mysterious of the four fundamental interactions, with its fundamental makeup unresolved despite successful classical and relativistic descriptions. This study investigates whether gravity acts purely as a geometric curvature of spacetime in the strong-field regime near the Galactic Center's supermassive black hole, SgrA*. We analyze high-precision astrometric and spectroscopic data from the GRAVITY instrument, focusing on S-star orbits. Our methodology employs a Bayesian framework to simultaneously fit Post-Newtonian parameters (gravitational redshift and Schwarzschild precession) and extended mass distributions (stellar cusp vs. dark matter spike), while rigorously characterizing instrumental systematics using K-band visibility data. We aim to distinguish true relativistic effects from astrophysical degeneracies and instrumental artifacts. Results are pending execution of the proposed MCMC analysis and injection-recovery validation protocols.

## Methods
1. Data Preprocessing: Calibrate raw K-band visibility amplitudes and fluxes using transfer function data. 2. Orbital Modeling: Implement a relativistic orbital integrator with 1st-order Post-Newtonian corrections as free scaling parameters. 3. Extended Mass Modeling: Incorporate stellar cusp and dark matter spike profiles to break degeneracy with PN parameters. 4. Bayesian Inference: Use affine-invariant MCMC to explore parameter space. 5. Validation: Perform injection-recovery tests on real K-band noise to validate systematic error handling.

## Experiments
### Baselines


```json
[
  "Pure Newtonian Gravity Model: Assumes no relativistic corrections; serves as the null hypothesis for strong-field deviations.",
  "Standard General Relativity (Fixed): Fixes PN parameters to exactly 1; used to calculate goodness-of-fit ($\\chi^2$) and residuals.",
  "Extended Mass Distribution Baseline (Stellar Cusp): Includes a distributed mass component modeled as a power-law stellar cusp to test if apparent relativistic effects are mimicked by local stellar density.",
  "Extended Mass Distribution Baseline (Dark Matter Spike): Includes a distributed mass component modeled as a dark matter spike to test if apparent relativistic effects are mimicked by dark matter accumulation."
]
```


### Metrics


```json
[
  "Posterior Mean and Credible Intervals for f_SP and f_GR: Quantifies deviation from GR predictions.",
  "Bayes Factor (K): Evaluates statistical preference for GR vs. alternative models.",
  "Reduced Chi-Squared ($\\chi^2_\\nu$): Assesses the goodness-of-fit for the best-fit model.",
  "Residual Autocorrelation: Checks for unmodeled systematic errors in time-series residuals."
]
```


### Ablation
1. Exclude Gravitational Redshift: Fit only astrometric precession to isolate spatial curvature effects.
2. Exclude Extended Mass: Fix extended mass to zero to test sensitivity of PN parameters to background potential assumptions.
3. Subset Analysis: Perform fits using only pre-2018 data vs. full dataset including pericenter passage to evaluate information gain from strong-field regime.

### Validation Protocol
1. Injection-Recovery Tests for Systematics: Inject synthetic orbital signals with known PN parameters into real K-band visibility noise data (EV-Q067-da43d6b6c21ff8d094c67551). If the recovery pipeline yields biased PN parameters correlated with visibility amplitude fluctuations, this indicates instrumental systematics rather than physical deviations. Successful recovery within error bars validates the distinction.
2. Cross-Validation: Split data by epoch (pre-pericenter vs. post-pericenter) to ensure consistency of derived parameters.
3. Systematic Error Budget: Propagate calibration uncertainties from K-band visibility data into final parameter posteriors.

## Results
当前状态：待执行验证实验。系统已生成可复现实验脚本、数据字段清单与评价指标，尚未运行真实实验。

## References
- **EV-Q067-da43d6b6c21ff8d094c67551** · arxiv · arXiv:2210.13095
  - authors: Not available · year: Not available
  - url: https://arxiv.org/pdf/2210.13095.pdf · doi: Not available
  - reliability_note: eligibility_status=FULLTEXT_VERIFIED; topic_relevance_status=DIRECT_QUESTION_CORE; locator=page:4|section:page-4|paragraph:1; content_sha256=14e9225871cae133516ffb39f10ebe750b2f163e1e887c120c8a39a3b225a874
- **EV-Q067-4dc4b7d0e3d42b5dfdd38565** · arxiv · arXiv:2211.11796
  - authors: Not available · year: Not available
  - url: https://arxiv.org/pdf/2211.11796.pdf · doi: Not available
  - reliability_note: eligibility_status=FULLTEXT_VERIFIED; topic_relevance_status=DIRECT_QUESTION_CORE; locator=page:1|section:page-1|paragraph:1; content_sha256=4f3080d8fbe45422c2a13feeda612074a8feda1fb419d0fa7d89c775a96f3f88
- **EV-Q067-6b5243bd87caa32ed2094f3a** · arxiv · arXiv:2006.08414
  - authors: Not available · year: Not available
  - url: https://arxiv.org/pdf/2006.08414.pdf · doi: Not available
  - reliability_note: eligibility_status=FULLTEXT_VERIFIED; topic_relevance_status=DIRECT_QUESTION_CORE; locator=page:2|section:page-2|paragraph:1; content_sha256=00e9942481b9b149f14fb8a1697f5a1d61cfffd75b7df5e2f1cf0580d6c58b8a
- **EV-Q067-16bec119afd02a3796e9eeed** · arxiv · arXiv:2303.17185
  - authors: Not available · year: Not available
  - url: https://arxiv.org/pdf/2303.17185.pdf · doi: Not available
  - reliability_note: eligibility_status=FULLTEXT_VERIFIED; topic_relevance_status=DIRECT_QUESTION_CORE; locator=page:1|section:page-1|paragraph:1; content_sha256=c3bcd81581c02146a385b2f68be25fdb826027c2bf9276ead2b4460741df844f

## Reviewer Comments
- Revision successfully addresses previous critical issues by explicitly defining 'Stellar Cusp' and 'Dark Matter Spike' as distinct baselines in the experiment design, directly resolving the degeneracy concern (Issue required_revision:6a4910a29343).
- Validation protocol now clearly specifies that Injection-Recovery Tests must use real K-band visibility noise (EV-Q067-da43d6b6c21ff8d094c67551) to distinguish instrumental systematics from physical signals, satisfying Issue required_revision:159a9f6ece58.
- All factual claims remain strictly grounded in allowed Evidence IDs; no hallucinated references or unverified causal links detected.
- Results field correctly maintains 'pending' status with no fabrication of experimental outcomes.
- Hypothesis remains falsifiable via Bayes Factor comparison against the newly specified extended mass baselines.

## Revision History
- auto_revision_1: 依据评审意见重做假设与实验设计。

## Reproducibility Checklist
- Archive raw GRAVITY visibility and flux data with DOI reference.
- Publish Python/Jupyter notebooks containing the relativistic orbital integrator and MCMC setup.
- Provide configuration files for the MCMC sampler (priors, step sizes, convergence criteria).
- Document the calibration pipeline for converting raw interferometric data to astrometric/spectroscopic observables.
- Release posterior samples and corner plots for all fitted parameters.
- Include code for generating synthetic injection-recovery tests using real noise properties.

