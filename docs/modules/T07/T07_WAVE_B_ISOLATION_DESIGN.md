# T07 Wave B Day 1: Question Isolation and Leakage Detection

Status: implemented and verified on `t07/b-batch-core`

Tested code SHA: `9dc00a8e3fbd8305976147b8df6a7a54fb0ba00c`

Integration SHA: `9dc00a8e3fbd8305976147b8df6a7a54fb0ba00c`

Wave A merge commit contained: `88e2f43c1bbe56d010691ff708f03567aaff30ef`

This document describes the reviewed Day 1 implementation. It is not the
repository-external scratch draft and it does not claim a formal or actual
125-question run. The only 125-job execution in this work was a marked
synthetic dry-run with zero provider calls and zero actual results.

## 1. Scope and invariants

Wave B adds an isolation sidecar and an auditable leakage detector without
changing the frozen Wave A `BatchJob`, `CheckpointRecord`, manifest, or runner
schema. The implementation enforces these invariants:

- each question has a unique workspace, context ID, memory namespace, cache
  namespace, and prompt namespace;
- question identity is bound to `batch_id`, `question_id`, `source_hash`, and
  canonical `input_hash`;
- a previous result must match the current question, source, and input hashes;
- retry uses the existing Wave A checkpoint compatibility policy;
- attempt-local memory, cache, prompt context, and previous-result state can be
  reset without changing immutable identity;
- exact contamination is blocking, while high similarity alone is an
  auditable non-blocking review signal;
- a dry-run record cannot be labeled as an actual result.

## 2. Scratch-to-Wave-A interface decisions

| Scratch interface | Final Wave A interface | Compatible | Required adaptation |
|---|---|---:|---|
| Candidate isolation identity | `BatchJob` identity and existing workspace/context/cache derivations | Partly | Keep memory and prompt namespaces in an additive sidecar; reproduce Wave A workspace, context ID, and cache namespace exactly. |
| Candidate `CheckpointLike` and retry checks | `CheckpointRecord`, `ResumePolicy`, and `resume_job` | No direct port | Remove the protocol and delegate source/input/question/route/model/prompt/schema/version validation to `resume_job`; verify the restored sidecar identity afterward. |
| Candidate `IsolationBoundaryError` | `BatchRunnerError` | No | Use the existing public error type and stable `error_code` field. |
| Candidate `previous_result` value | No Wave A job field | Partly | Represent it as `QuestionScopedResult`, bound to question/source/input and deep-copied into attempt-local context. |
| Candidate memory and prompt fields | No Wave A `BatchJob` fields | Partly | Keep them as deterministic `QuestionIsolationIdentity` sidecar fields; do not upgrade `t07.batch.v1`. |
| Candidate leakage detector | `detect_cross_question_contamination` and `ContaminationFinding` | Partly | Call the Wave A detector for its three frozen codes, then adapt those results into the extended Pydantic finding shape and add six Wave B checks. Do not overwrite `contamination.py`. |
| Candidate finding dataclass | Existing Pydantic-based contract style | No direct port | Use a frozen Pydantic `LeakageFinding` with ten explicit audit fields and a computed finding count. |
| Candidate completion hook | Wave A `gates_pending` lifecycle, with no owner-approved scheduler hook | Not yet | Expose `evaluate_completion_gate` as an explicit sidecar decision. Do not modify the runner or transition state automatically. |
| Candidate hypothesis text | No named hypothesis field in the Wave A `OutputContract` | Not schema-compatible | Accept hypothesis only through the explicit fingerprint/leakage adapter. Do not add a required output-contract field. |
| Candidate fingerprint algorithm | No persisted Wave A fingerprint schema | Additively compatible | Keep hashes ephemeral and auditable; do not reinterpret old checkpoints or persist a new schema version. |

The result is deliberately additive. `app/contracts/batch.py`,
`app/batch/runner.py`, `app/batch/checkpoint.py`, and
`app/batch/contamination.py` remain unchanged.

## 3. Isolation identity

`QuestionIsolationIdentity` contains:

| Field | Derivation or source | Boundary |
|---|---|---|
| `batch_id` | Wave A `BatchJob.batch_id` | parent run |
| `question_id` | Wave A `BatchJob.question_id` | question owner |
| `source_hash` | Wave A source SHA-256 | source snapshot |
| `input_hash` | Wave A canonical input SHA-256 | exact question input |
| `workspace` | `<batch>/<question>/workspace` | filesystem |
| `context_id` | `ctx:<batch>:<question>:<input_hash[:16]>` | execution context |
| `cache_namespace` | `cache:<batch>:<question>:<input_hash[:16]>` | Wave A cache |
| `memory_namespace` | `memory:<batch>:<question>:<sidecar_digest[:20]>` | mutable memory |
| `prompt_namespace` | `prompt:<batch>:<question>:<sidecar_digest[:20]>` | assembled prompt |
| `isolation_version` | `t07.isolation.v1` | derivation version |

The sidecar digest is SHA-256 over canonical UTF-8 JSON with sorted keys and
compact separators. Its inputs are batch ID, question ID, source hash, input
hash, and isolation version. Python's randomized `hash()` is never used.
Readable batch/question segments remain in every namespace, so distinct
questions cannot share a namespace merely because a shortened digest collides.

Construction also verifies that the supplied Wave A job already contains the
canonical workspace, context ID, and cache namespace. Forged or stale fields
fail closed.

## 4. Mutable-state lifecycle and boundaries

1. Build and validate the frozen sidecar identity from a real `BatchJob`.
2. Create fresh `memory`, `cache`, and `prompt_context` dictionaries for the
   question. Caller-supplied prompt data is deep-copied.
3. Accept a `QuestionScopedResult` only when question ID, source hash, and
   input hash all match the active identity; its payload is deep-copied.
4. Validate all active contexts for namespace collisions and Python object
   aliasing before sharing them with processors.
5. For retry, first compare the sidecar with the expected job, then call Wave
   A `resume_job`, which checks batch/question/source/input/route/model/prompt/
   schema/status/attempt compatibility. Rebuild the identity from the returned
   deep copy and compare again.
6. Reset attempt-local dictionaries and the previous result in place while
   preserving the frozen identity object.

The cache namespace remains the Wave A namespace. Memory and prompt namespaces
are additive sidecar fields. `previous_result` is attempt-local and is never
stored as an unbound arbitrary payload.

## 5. Normalization and SHA-256

Scientific text normalization is deterministic:

1. reject non-string input;
2. apply Unicode NFKC normalization;
3. apply Unicode-aware `casefold()`;
4. replace every Unicode punctuation character with a token boundary;
5. collapse whitespace and trim both ends.

Each normalized title, abstract, and hypothesis is hashed independently as
UTF-8 SHA-256. The combined hash is SHA-256 over canonical JSON containing the
three normalized fields with sorted keys and compact separators. Question ID
is intentionally excluded from content hashes so identical content across
questions remains detectable.

## 6. Similarity algorithm and threshold

For each non-empty field the implementation records token-set Jaccard overlap,
`SequenceMatcher` ratio, exact hash equality, and whether template removal
leaves no substantive content. A non-template exact match scores `1.0`;
otherwise the field score is:

`0.4 * token_overlap + 0.6 * sequence_similarity`

The combined score is a normalized weighted mean over active fields:

- title: `0.25`;
- abstract: `0.50`;
- hypothesis: `0.25`.

Empty or template-only fields are excluded from the denominator. Only
different question IDs are compared. A same-question retry returns
`compared=false` and cannot produce a cross-question similarity finding.

The current research threshold is strictly `combined_score > 0.90`. Crossing
it emits `HIGH_CROSS_QUESTION_SIMILARITY` with severity `review` and
`blocks_completion=false`. This signal is not itself proof of contamination.
The weights, template phrases, and threshold require calibration on labeled
authoritative outputs before production use.

## 7. Finding structure and detector composition

Every frozen `LeakageFinding` has exactly:

- `finding_code`, `severity`, `question_ids`, and `field`;
- `observed_value` and structured `evidence`;
- optional `similarity_score` and `threshold`;
- `blocks_completion` and `message`.

`LeakageScanResult.finding_count` is computed from `len(findings)`; it is not a
stored counter or fixture constant.

The detector first calls Wave A `detect_cross_question_contamination`, keeping
its three frozen behaviors:

- `CROSS_QUESTION_CONTENT_REUSE`;
- `CROSS_QUESTION_EVIDENCE_ID_REUSE`;
- `OUTPUT_QUESTION_ID_MISMATCH`.

It then adds:

- `CACHE_NAMESPACE_COLLISION`;
- `MEMORY_NAMESPACE_COLLISION`;
- `PREVIOUS_RESULT_REUSE`;
- `PROMPT_CONTEXT_REUSE`;
- `KEYWORD_LEAKAGE`;
- `HIGH_CROSS_QUESTION_SIMILARITY`.

The marked synthetic Q901/Q902/Q903 fixture produces nine actual findings:
eight blockers and one similarity-review finding. It also proves that all
three Wave A findings remain detectable and that Q901/Q902 pandemic-plan reuse
is reported. These are controlled synthetic cases, not historical or formal
contamination incidents.

## 8. Completion gate

`evaluate_completion_gate` separates findings by their explicit
`blocks_completion` flag. Any exact reuse, identity mismatch, namespace
collision, previous-result reuse, prompt-context reuse, or owned-keyword
leakage denies completion. High similarity alone remains visible for human
review and does not deny completion.

The decision is intentionally not wired into `BatchRunner`: Wave A has no
approved scheduler/completion hook that owns the new sidecar. A later change
must attach this explicit decision before `gates_pending -> completed`, retain
the findings as question-scoped evidence, and add state-transition tests.

## 9. False-positive risks

- shared scientific boilerplate or standard report headings;
- short titles and common domain vocabulary;
- intentionally shared prompt templates whose question payloads differ;
- evidence identifiers that another contract defines as globally reusable;
- punctuation normalization that changes meaningful scientific notation;
- keywords without authoritative ownership metadata;
- translated or paraphrased text with a high sequence score.

Mitigations are non-blocking similarity review, field-level component scores,
explicit evidence, template exclusion, question-owned keyword metadata, and
future threshold calibration. Exact rules must not be weakened merely to
reduce similarity-review volume.

## 10. Wave A compatibility, provenance, and validation

No Wave A schema or checkpoint version was changed. The final validation used
Python 3.12.10 at
`D:\SAGE125-AI-Scientist\.venv\Scripts\python.exe`.

Before migration, the formal baseline was:

- `tests/batch`: 45 passed in 7.52s;
- full pytest: 710 collected, 672 passed, 37 skipped, 1 failed in 84.13s;
- first baseline failure:
  `tests/api/test_delivery_smoke.py::test_streamlit_entrypoint_executes_without_exception`,
  a 30-second Streamlit `AppTest` timeout outside the T07 owner path;
- the focused smoke-test rerun passed: 1 passed in 26.16s.

The baseline failure is retained as observed evidence. It was not changed by
T07 code. The final full suite did not reproduce it.

Test-first and final results:

- formal RED: 44 collected, 1 passed, 43 failed in 0.45s; first failure was
  missing `app.batch.isolation`;
- final focused Wave B tests: 44 passed in 0.29s;
- final `tests/batch`: 89 passed in 7.53s;
- final full pytest: 754 collected, 717 passed, 37 skipped, 0 failed in 58.82s;
- synthetic 125-job dry-run: 125 unique workspaces, contexts, and caches;
  0 provider calls and 0 actual results.

## 11. Adopted, rewritten, and deferred scratch work

Adopted after review: the additive sidecar direction, deterministic namespace
concept, normalization/fingerprint algorithm, explainable similarity scoring,
nine finding codes, completion-gate separation, three focused test groups, and
the explicitly marked synthetic leakage fixture.

Rewritten for the final Wave A interfaces: error handling, checkpoint retry,
job construction, source/input binding, Pydantic finding serialization, Wave A
detector reuse, test fixtures, and the formal design/provenance text.

Not migrated: scratch `__pycache__` files, syntax records, draft status and old
snapshot SHA, candidate output-layout/validation/delivery-index modules and
tests, the five-question output fixture, and the real-five execution plan.
Those are later-day candidates and were outside Day 1 scope.

## 12. Rollback

The change is additive. Rollback consists of removing the three Wave B modules,
their package exports, the synthetic audit CLI, the three focused tests and
fixture, and the Wave B Day 1 documentation/evidence. Wave A runner,
checkpoint, contract, and contamination behavior remain intact. If a future
completion integration proves unsafe, disconnect the completion-gate adapter
first and retain findings as diagnostics; do not reinterpret or rewrite
existing Wave A checkpoints.
