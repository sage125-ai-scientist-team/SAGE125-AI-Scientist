# T07 Wave C Offline Hardening

Date: 2026-08-14
Branch: `t07/c-batch-hardening`
Integration baseline: `5aa8460bae108761a67ba52bd980b013cf27ff3c`
Wave B merge commit: `cff5be5ef6a7e6956d38600a18f7cff8b4473fce`

## Outcome

Wave C now has a provider-free monitoring and final-package validation layer.
It does not generate research content and cannot turn partial, synthetic, Mock,
or structurally invalid output into a final package.

The implementation adds:

- a read-only status snapshot derived from `manifest.json` and
  `delivery_index.json`;
- an atomic pause request checked before the next formal executor call;
- a hash-bound pause release archived under `pause_history/` before resume;
- physical SHA-256 validation for every indexed artifact;
- a separately supplied, operator-hash-pinned trusted execution receipt that
  binds the root manifest, delivery index, every question input/source, and
  every required physical artifact to the run being validated;
- exact `Q001` through `Q125` directory, record, and manifest checks;
- completed/actual/non-Mock/production enforcement for every question;
- validation of checkpoint, completion decision, artifact manifest, and
  token-only `llm_call_audit.json` identity;
- content-level revalidation of question identity, non-empty document-backed
  evidence, runtime content hashes, hypothesis/evidence bindings, citations,
  T01/T03 gate receipts, PDF structure, and cross-question evidence reuse or
  similarity above `0.90`;
- a deterministic 24-question sample plan that remains explicitly
  `pending_human_review`;
- UTF-8, atomic status/checksum/sample receipts;
- a provider-free CLI at `python -m scripts.batch_125.wave_c`.

## Commands

```powershell
python -m scripts.batch_125.wave_c status --batch-root <external-batch-root>

python -m scripts.batch_125.wave_c pause `
  --batch-root <external-batch-root> `
  --requested-by <operator> `
  --reason <reason>

python -m scripts.batch_125.wave_c resume `
  --batch-root <external-batch-root> `
  --released-by <operator> `
  --expected-pause-sha256 <sha256>

python -m scripts.batch_125.wave_c validate `
  --batch-root <external-batch-root> `
  --expected-code-sha <tested-code-sha> `
  --trusted-receipts <external-trusted-receipts.json> `
  --expected-trusted-receipts-sha256 <operator-supplied-sha256> `
  --write-receipts
```

None of these commands invokes a Provider. The formal runner checks the pause
marker immediately before starting the next question executor.

The trusted receipt must be a regular file outside the candidate batch root.
Its schema is `t07.wave-c-trusted-receipts.v1`. The validator refuses a missing,
unhash-pinned, self-contained, wrong-batch, wrong-code, partial, reordered, or
artifact-mismatched receipt. This makes a candidate package's own
`actual_execution`/`synthetic` claims insufficient to pass final validation.

## Validation

- Targeted Wave C validator tests: `19 passed`, `0 failed`, `93.48s`.
- Long Windows path pause/resume regression: `1 passed`, `0 failed`, `0.98s`.
- `tests/batch`: `339 passed`, `2 skipped`, `0 failed`, `133.77s`.
- Native lint: passed, no failures.
- Native type contract: passed, no failures.
- Full pytest: `1452 passed`, `41 skipped`, `3 failed`, `175.45s`.

The three full-suite failures are outside T07 and are preserved as environment
blockers: `tests/integration/test_t09_b001_quality_gates.py` cannot import the
locally absent `ruff` and `coverage` modules. No dependency, T09, skip, xfail,
timeout, or assertion was changed.

## Formal completion status

The Wave C machine-validation hardening is complete, but the formal scientific
deliverable is not represented as complete:

- no 125-question Provider run was executed in this work;
- `provider_calls=0` for all Wave C validation activity;
- no complete real Evidence Context source is available to this worktree;
- no 125/125 actual package exists for the validator to approve;
- no external trusted receipt for a 125/125 actual run has been supplied;
- the deterministic 24-question plan is not human sign-off;
- no PR Ready or merge claim is made.

The next formal run remains fail-closed until an approved real evidence source,
explicit Provider authorization, an external run root, and an independently
hash-pinned trusted execution receipt are supplied. Only a physical 125/125
package that passes this validator may advance to the still-required 24-question
human audit.
