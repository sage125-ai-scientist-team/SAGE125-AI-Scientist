# T05 Wave B: formal WDBC Round 1

## Outcome

The formal Round 1 baseline completed through `LocalProcessRunner` with
`mode=actual`, a registered `scientific` entrypoint, a clean Git provenance
record, and validated dataset, artifact, and metric evidence. It is a research
workflow demonstration and is not suitable for clinical diagnosis or care.

The source execution commit is
`18c86f1e1963b13cbed09356201d92f38a2a2880`. The persisted typed evidence is
`docs/modules/T05/round1/execution_result.json`.

## Pinned input and method

- Dataset: UCI Breast Cancer Wisconsin (Diagnostic), version `1995-10-31`.
- License: CC-BY-4.0; attribution and source URLs remain in
  `experiments/flagship/dataset_manifest.json`.
- Pin: SHA-256
  `d606af411f3e5be8a317a5a8b652b425aaf0ff38ca683d5327ffff94c3695f4a`,
  size 124103 bytes.
- Raw source rows are downloaded to ignored local cache and are not committed.
- Model: standardized full-batch logistic regression implemented with NumPy.
- Split: deterministic, stratified holdout; seed 125; test fraction 0.2.
- Fixed Round 1 parameters are in
  `experiments/flagship/round1_config.json`.

The baseline script validates the approved byte pin, 569 rows, 32 columns, 30
finite numeric features, unique identifiers, labels, and class counts before it
writes any output. Feature normalization is learned from the training split
only.

## Observed results

| Evidence | Observed value |
| --- | ---: |
| Train records | 456 |
| Holdout records | 113 |
| Balanced accuracy | 0.9642857142857143 |
| Malignant recall | 0.9285714285714286 |
| True negative / false positive | 71 / 0 |
| False negative / true positive | 3 / 39 |

These values come from runner-validated `source=observed` metric artifacts;
they were not transcribed into the execution result by hand.

## Reproduction

From a clean checkout of the source execution commit, using the pinned project
environment:

```powershell
$Python = (Resolve-Path ".\.venv\Scripts\python.exe").Path
& $Python -X utf8 -m app.execution.run_round1 `
  --cache-root data/cache/t05-wdbc `
  --package-dir exports/t05-round1-reproduction
```

After the first verified download, add `--offline` to require a cache-only
revalidation and run. The committed formal run was reproduced offline from the
same clean source commit; all eight scientific artifact SHA-256 values and
sizes matched the online run. Runner timestamps and execution IDs are expected
to differ, so reproducibility is asserted on the scientific artifacts rather
than byte identity of the envelope.

The command refuses to overwrite an existing package. Remove or choose a new
ignored `exports/` destination deliberately; do not overwrite the committed
evidence.

## Package and downstream contract

`docs/modules/T05/round1/package_manifest.json` indexes every package file
by relative path, SHA-256, and size. The package contains:

- `execution_spec.json` and `execution_result.json` for typed T02 consumption;
- observed metric JSON for balanced accuracy and malignant recall;
- predictions and confusion-matrix CSV tables;
- a deterministic SVG metric plot;
- the fitted model parameters, raw run summary, and Round 2 plan;
- bounded stdout/stderr logs, environment/Git metadata, and a package index.

`consumer_mapping.json` explicitly maps artifact ID, kind, media type, unit,
and validation status. This closes the T06 CSV/SVG wiring note without adding
fields to `DatasetManifest`: those fields belong to execution artifact and
metric contracts.

T05 does not modify T02-owned pipeline code. Downstream code must parse and
revalidate the persisted `ExecutionResult`; it must not infer success from a
file name, truthy dictionary, or status string alone.

## Round 1 to Round 2 decision

The predeclared malignant-recall target was 0.95. The observed Round 1 value
was 0.9285714285714286, so the sole proposed Round 2 change is to lower the
decision threshold from 0.5 to 0.4 while retaining seed 125 and the same split.
The machine-readable plan is `artifacts/round2-plan.json`.

Round 2 has not been executed in this PR. The plan explicitly records
`formal_round2_executed=false`; results must only be added after Wave C performs
that controlled run.

## Failure behavior

`experiments/flagship/failure_injection_report.json` records the exact timeout,
resource-capability, path, bad-data, dependency, repeat-run, artifact-integrity,
and cleanup tests. Failures cannot set `actual_execution=true`. CPU, memory,
network, and GPU isolation are not falsely claimed by the Windows process
backend; complete hostile-code isolation remains a future container-backend
capability.
