# T02 C007 Readiness Hardening

Status: T02-owned readiness controls implemented; frozen C007 cases remain blocked.

This document records readiness behavior only. It is not C007, METRIC004, C008,
or C009 acceptance evidence, and it does not authorize a Provider call or a case
rerun.

## Frozen authority consumed by T02

- `FROZEN_MODEL_POLICY=TIERED_ROUTE_ALLOWED`
- `AUTHORIZED_MODELS=[qwen3.6-flash,qwen3.7-plus,qwen3.7-max]`
- `C007_ACTUAL_REQUIREMENT=T05_EXECUTION_RESULT_REQUIRED`
- `T06_MULTIMODAL_EVIDENCE_REQUIRED=YES`
- `C007_CROSS_OWNER_PAIRING_POLICY=FROZEN_V1`

The exact fields take precedence. Retained legacy aliases are accepted only through
the explicit `LEGACY_ALIAS` compatibility path. Unknown policies, unauthorized
models, missing T06 or pairing authority, unknown pairing policies, and misspelled
keys fail closed. The pairing authority is bound to Captain comment
`issuecomment-5300864125`.

Current authority state is distinct from per-case input readiness:

- `PAIRING_AUTHORITY_READY=YES`
- `PAIRING_AUTHORITY_REQUIRED=NO`
- `PAIRING_POLICY=FROZEN_V1`
- `ALL_PAIRINGS_READY=NO`

The last value remains `NO` because no frozen case currently has both eligible T05
and T06 inputs. It does not mean Captain authority is missing.

## T02-owned controls completed

1. `FormalCaseInput` binds each frozen question and logical label set to typed T05
   `ExecutionResult`, typed T06 `MultimodalArtifact` values, source commit/run/input
   identities, artifact checksums, and Captain pairing provenance.
2. A public persisted-T05 boundary refuses an ordinary JSON/dict rehydration when
   no public verified loader is named. T02 does not import or reconstruct private
   T05 runner attestation.
3. The formal input gate evaluates T05 actual execution and provenance, T06
   actual/non-fixture provenance and consumer projection, and cross-owner pairing.
   One eligible bundle is required for each of Q028, Q095, Q045, and Q100.
4. Formal evidence stores separate canonical hashes for the T05 result and consumer
   summary, per-artifact and aggregate T06 source hashes, and per-artifact and
   aggregate T06 consumer-summary hashes. Local absolute path roots and secret-like
   fields are excluded from accepted canonical hash material.
5. `FormalRevisionContextBinding` verifies the exact execution and multimodal
   summary projections injected into the same `RevisionContext`. The deterministic
   impact trace links source hashes, context fingerprint, next-prompt hashes, V2
   version, structured change IDs, and affected plan sections. An unlinked source is
   `UNPROVEN` and cannot pass.
6. The tiered route audit retains the complete non-mock call ledger, total and
   per-model counts, stage and round mappings, call identity/status/timestamps, and
   unauthorized call count. Any model outside the three frozen identities blocks
   acceptance.
7. The FROZEN_V1 pairing record locks `question_id` and
   `canonical_input_sha256`, T05/T06 source commits and run identities, declared
   checksums and their verification status, and Reviewer question/run/target-version
   lineage. It emits explicit `SAME_RUN|DIFFERENT_RUN`,
   `SAME_COMMIT|DIFFERENT_COMMIT`, checksum, result, and failure fields.
8. Cross-run pairing is denied by default. It is allowed only when the Captain case
   row sets `allow_cross_run_pairing=true` and both owner inputs carry the exact
   frozen case `pairing_id`. Cross-commit pairing permits the same commit directly;
   different commits require either an exact Captain allowlist or successful Git
   ancestry checks against the Captain-attested integration tip. Missing fields,
   failed checksum verification, mock/fixture/synthetic/planned/expected evidence,
   or unprovable lineage fail closed. Text similarity, timestamps, and path proximity
   are never pairing evidence.

## Fail-before-Provider invariant

`run_formal_release(..., formal_case_inputs=...)` evaluates the complete four-case
typed input set before Provider preflight. A missing, duplicate, or ineligible input
produces `BLOCKED_FORMAL_INPUTS`, per-case blockers, `provider_calls=0`, and
`pipeline_real_calls=0`. `execute_formal_case(...)` repeats the per-case eligibility
check before importing or invoking the pipeline and passes only the exact validated
typed objects to the existing T05 and T06 hooks.

Q028 has exactly one input bundle and one raw result with
`logical_labels=(Q028_REGRESSION, FLAGSHIP)` and `shared_run=true`; the evidence is
not duplicated to satisfy the five-logical/four-unique-run rule.

## External blockers that remain

T05:

- Q028 needs a public, verified, fail-closed loader for its persisted actual
  `ExecutionResult`.
- Q095, Q045, and Q100 need eligible actual `ExecutionResult` values.

T06:

- Q028, Q095, Q045, and Q100 need actual, non-fixture `MultimodalArtifact` values
  with portable provenance and pairing checksums.

Therefore:

- `PAIRING_AUTHORITY_READY=YES`
- `PAIRING_AUTHORITY_REQUIRED=NO`
- `PAIRING_POLICY=FROZEN_V1`
- `ALL_T05_READY=NO`
- `ALL_T06_READY=NO`
- `ALL_PAIRINGS_READY=NO`
- `ALL_CASES_READY_FOR_RERUN=NO`
- `READY_FOR_FINAL_CASE_RERUN=NO`
