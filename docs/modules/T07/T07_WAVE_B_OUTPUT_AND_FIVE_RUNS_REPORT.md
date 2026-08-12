# T07 Wave B Day 2: Output Contract and Five-Run Report

Status: `FIVE_REAL_RUNS_BLOCKED`

Five real runs: `FIVE_REAL_RUNS_NOT_EXECUTED`

Branch: `t07/b-batch-core`

Tested base HEAD: `730f4c96cb856b3de1cbb83778445f0b1f9f202b`

Integration SHA: `9dc00a8e3fbd8305976147b8df6a7a54fb0ba00c`

Integration comparison: `ahead=2`, `behind=0`

Validation date: `2026-08-02` (`Asia/Shanghai`)

Environment: Windows / PowerShell / Python 3.12.10

Python executable:
`D:\SAGE125-AI-Scientist\.venv\Scripts\python.exe`

The implementation and tests were executed from the uncommitted Day 2 working
tree based on the HEAD above. No provider or model was called, no actual result
was generated, and no synthetic fixture was relabeled as authoritative.

## 1. Implemented scope

Day 2 adds three modules without changing the frozen Wave A `BatchJob`,
`CheckpointRecord`, batch schema, checkpoint schema, runner, or Day 1 leakage
behavior:

- `output_layout.py`: deterministic question-owned paths and boundary checks;
- `output_validation.py`: physical file, JSON identity, output-contract, PDF,
  actual-completion, and artifact-manifest validation;
- `delivery_index.py`: per-question delivery records, derived summaries,
  canonical checksum, JSON round-trip, and optional physical hash checks.

All new public failures reuse `BatchRunnerError(error_code, message)`. The
scratch-only `OutputLayoutError`, `OutputValidationError`, and
`DeliveryIndexError` classes were not migrated.

## 2. Output directory structure

For a batch root and question ID, `build_question_output_paths` derives:

```text
<batch_root>/
  manifest.json
  <question_id>/
    report.pdf
    report.md
    result.json
    evidence_cards.json
    agent_trace.json
    artifact_manifest.json
```

`manifest.json` remains the Wave A batch manifest. The five Wave A required
artifacts are report PDF/Markdown and the three JSON files.
`artifact_manifest.json` has a deterministic path but is intentionally
excluded from the five-artifact hash list so its checksum is not recursive.

Path rules:

- `question_id` must be one safe relative segment and cannot be a Windows
  reserved name;
- absolute paths, `..`, cross-question roots, forged `QuestionOutputPaths`,
  and retry-to-another-question attempts are rejected;
- every target must remain inside both the batch root and owning question
  root after resolution;
- symlink components and symlink artifact files are rejected;
- the same batch/question inputs always produce the same tree.

## 3. Artifact validation rules

`validate_required_artifacts` verifies:

1. all five required artifacts exist;
2. every artifact is a non-empty regular file, not a directory or symlink;
3. `result.json` and `agent_trace.json` are UTF-8 JSON objects;
4. `evidence_cards.json` is a UTF-8 JSON array of auditable evidence objects;
5. each JSON record matches the job's `batch_id`, `question_id`, `attempt`,
   `source_hash`, `input_hash`, and `status`;
6. result fields contain and match all eleven Wave A standard output fields;
7. declared contract artifact paths exactly equal
   `<batch_id>/<question_id>/<artifact_name>`;
8. `report.pdf` begins with the `%PDF-` signature;
9. every artifact SHA-256 is streamed from its physical file bytes;
10. failed validation cannot produce an artifact manifest.

`validate_actual_completion` passes only for a `completed/actual`, non-Mock,
production job whose physical validation passed. Synthetic, Mock, planned,
expected, non-completed, incomplete, or invalid output fails closed.

Stable error codes covered by executable tests:

- `OUTPUT_PATH_INVALID`
- `REQUIRED_ARTIFACT_MISSING`
- `ARTIFACT_EMPTY`
- `ARTIFACT_SYMLINK_REJECTED`
- `ARTIFACT_JSON_INVALID`
- `ARTIFACT_QUESTION_MISMATCH`
- `ARTIFACT_BATCH_MISMATCH`
- `ARTIFACT_PROVENANCE_MISMATCH`
- `PDF_SIGNATURE_INVALID`
- `ACTUAL_STATUS_INVALID`
- `OUTPUT_CONTRACT_INCOMPLETE`

## 4. Artifact manifest

`ArtifactManifest` records:

- batch ID and question ID;
- output contract version;
- validation status;
- five sorted artifact records containing name, question-relative path,
  physical SHA-256, and positive byte size;
- `manifest_sha256`.

The checksum hashes canonical UTF-8 JSON with sorted keys and compact
separators. The checksum payload excludes `manifest_sha256`, so it is
non-self-referential and deterministic.

## 5. Delivery index fields and derivation

Each `QuestionDeliveryRecord` contains:

- `batch_id`, `question_id`, `status`;
- `source_hash`, `input_hash`;
- `output_contract_version`, `schema_version`;
- route ID, provider, model, model version, prompt version, and prompt hash;
- artifact names, paths, physical SHA-256 values, and byte sizes;
- input tokens, output tokens, total accounted tokens;
- duration seconds and attempts;
- latest failure code;
- validation status and error codes;
- result kind plus derived actual/Mock/synthetic/completed flags.

`completed` is recomputed from status, provenance, validation, route, and the
exact five-artifact set. A caller cannot pass a completed flag to
`build_question_delivery_record`. Direct deserialization is also checked
against the same derivation rule.

`DeliveryIndex` contains index version, batch ID, sorted records, `total`,
`status_counts`, `completed`, and `index_sha256`. All three summaries are
derived from records. Duplicate question IDs and cross-batch records are
rejected. The index checksum excludes its own checksum field and is independent
of input record order. Optional physical validation rehashes every indexed
file and rejects missing files, traversal, symlinks, root escape, or hash
mismatch.

## 6. Synthetic fixture scope

`tests/batch/fixtures/five_question_outputs.synthetic.json` declares:

```text
synthetic=true
mock=true
formal_run=false
actual_execution=false
model_provider_called=false
authoritative_source_verified=false
```

Its Q901-Q905 records exist only to exercise layout, validation, and index
behavior. They are not the formal five-question package and contain no actual
research output.

## 7. Five-real-run preflight

| Gate | Observed state | Result |
|---|---|---|
| Authoritative `questions_125.json` | Neither `data/processed/questions_125.json` nor repository-root `questions_125.json` exists; no non-synthetic tracked catalog was found. | BLOCKED |
| Five IDs from authoritative source | Cannot select or hash five authoritative records while the catalog is absent. | BLOCKED |
| Schema version | `t07.batch.v1` remains frozen. | PASS |
| Provider/model/prompt versions | The only T07 runner route is `dry-run/none/none/unassigned`; no formal route or prompt hash is frozen. | BLOCKED |
| Secure local credentials | Presence-only checks found no `DASHSCOPE_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `QWEN_API_KEY`; no value was read or logged. Provider is also unresolved. | BLOCKED |
| Token/cost caps | Existing defaults are zero for dry-run; no approved non-zero five-run token and cost ceiling exists. | BLOCKED |
| T01/T03 completion gates | Repository contracts/services exist, but no frozen T07 formal-run adapter proves that required T01 evidence and T03 quality results gate each question before completion. | BLOCKED |
| Output excluded from Git | `.pytest_tmp/` is locally ignored and can contain a future authorized run without entering Git. | PASS |
| No synthetic fallback | Wave A loader rejects missing/unmarked sources and rejects synthetic-as-production. | PASS |

Because at least one mandatory gate failed, no model/provider invocation was
attempted. No question IDs, output tokens, cost, retries, artifact hashes, or
completion results exist for five real questions.

## 8. Test-first evidence

Formal RED before implementation:

- command: the three Day 2 test files;
- exit code 1;
- 62 collected, 60 failed, 1 passed, 1 skipped, 0 warnings;
- duration 0.70s;
- first failure: missing `app.batch.output_layout`;
- the one pass was fixture provenance; the one skip was Windows native symlink
  privilege error 1314.

Final validation:

| Command | Exact result |
|---|---|
| three Day 2 test files | exit 0; 64 collected; 62 passed, 2 skipped, 0 failed, 0 warnings in 1.08s |
| `pytest -q tests/batch` | exit 0; 153 collected; 151 passed, 2 skipped, 0 failed, 0 warnings in 8.09s |
| `pytest -q` | exit 0; 818 collected; 779 passed, 39 skipped, 0 failed, 0 warnings in 57.50s |

The two Day 2 skips are native Windows symlink-creation probes. Separate
monkeypatched tests verified both symlink rejection paths without OS privilege
and passed. The other 37 full-suite skips are the existing missing-source,
booklet, and execution symlink-capability cases.

## 9. Current status and rollback

Output layout, validation, manifest, and delivery-index code is implemented
and synthetic negative-test complete. The five actual runs remain blocked and
unexecuted until every preflight blocker is resolved and explicit model use is
authorized.

The change is additive. Rollback removes the three Day 2 modules, their public
exports, the three Day 2 tests and synthetic fixture, and this Day 2 evidence.
Wave A and Wave B Day 1 behavior and serialized contracts remain unchanged.
