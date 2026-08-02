# T07 Day 2 Batch Contract Implementation Plan

> **For agentic workers:** Execute this plan inline with
> `superpowers:test-driven-development`; every production behavior begins with
> a failing test. Do not commit, push, create a PR, or modify files outside the
> declared owner paths.

**Goal:** Deliver a stable Pydantic batch contract and a deterministic,
no-provider 125-job dry-run skeleton with atomic checkpoints, retry limits,
resume compatibility, and reproducible test evidence.

**Architecture:** An explicit production or marked-synthetic JSON source is
validated and canonically hashed. `BatchRunner` creates independent job
identities, writes per-job checkpoints atomically, and atomically writes a
manifest; real workflow execution is outside Day 2.

**Tech Stack:** Python 3.12, Pydantic v2 already present in the repository,
pytest, standard-library JSON/hash/path/tempfile/fsync/replace.

## Global Constraints

- Modify only `app/batch/**`, `scripts/batch_125/**`,
  `app/contracts/batch.py`, `tests/batch/**`, and `docs/modules/T07/**`.
- Do not add dependencies or change prompt/model versions.
- Do not call a provider or external API.
- Do not create a synthetic fallback for a missing production source.
- Do not claim authoritative 125-question validation or historical
  contamination reproduction.
- Do not commit, push, create/ready/merge a PR, rebase, or force-push.

---

## File map

| File | Responsibility |
|---|---|
| `app/contracts/batch.py` | Enums and Pydantic models for manifest, job, budget, retry, resume, route, output, checkpoint, and failure records. |
| `app/batch/errors.py` | Stable `BatchRunnerError(error_code, message)` boundary. |
| `app/batch/checkpoint.py` | Atomic JSON persistence, checkpoint validation, and resume compatibility. |
| `app/batch/runner.py` | Explicit source loading, canonical hashes, 125 isolated jobs, failure bookkeeping, dry-run manifest/checkpoints. |
| `app/batch/__init__.py` | Public Day 2 imports only. |
| `scripts/batch_125/dry_run.py` | CLI for explicit synthetic or production dry-run. |
| `scripts/batch_125/__init__.py` | Package marker. |
| `tests/batch/fixtures/questions_125.synthetic.json` | Marked synthetic Q001-Q125 catalog. |
| `tests/batch/test_contract.py` | Contract validation and JSON round-trip tests. |
| `tests/batch/test_runner.py` | Dry-run, isolation, missing-source, retry, checkpoint, and resume tests. |
| `docs/modules/T07/evidence/day2_*.txt` | Exact RED, GREEN, full-suite, and synthetic CLI output. |

### Task 1: Contract RED

**Interfaces**

- Produces tests for `JobStatus`, `ResultKind`, `SourceKind`,
  `FailureRecord`, `ModelRoute`, `BatchBudget`, `RetryPolicy`,
  `ResumePolicy`, `OutputContract`, `BatchJob`, `CheckpointRecord`, and
  `BatchManifest`.
- JSON uses Pydantic `model_dump_json()` and `model_validate_json()`.

- [ ] Add tests that dynamically import the absent contract inside each test,
  so pytest reports behavior failures rather than a collection error.
- [ ] Prove a manifest with two jobs sharing `question_id="Q001"` raises a
  Pydantic validation error.
- [ ] Prove a valid one-job manifest survives JSON round-trip equality.
- [ ] Prove `mock=true/status=completed` is rejected.
- [ ] Prove `status=completed` with an empty output contract is rejected.
- [ ] Run:

  ```powershell
  & ".\.venv\Scripts\python.exe" -m pytest -q tests/batch
  ```

  Expected RED cause: `ModuleNotFoundError` for the not-yet-created T07
  contract/runner modules.

### Task 2: Runner RED

**Interfaces**

- `BatchRunner(run_root: Path, provider: Callable | None = None)`
- `BatchRunner.dry_run(source_path: Path, *, batch_id: str,
  source_kind: SourceKind) -> BatchManifest`
- `register_failure(job: BatchJob, *, error_code: str, message: str,
  retryable: bool) -> BatchJob`
- `write_checkpoint(path: Path, checkpoint: CheckpointRecord) -> None`
- `read_checkpoint(path: Path) -> CheckpointRecord`
- `resume_job(checkpoint: CheckpointRecord, expected_job: BatchJob,
  policy: ResumePolicy) -> BatchJob`

- [ ] Add the marked synthetic JSON object with literal IDs `Q001` through
  `Q125`; every record contains a clearly synthetic question string.
- [ ] Prove dry-run returns exactly 125 jobs and all workspace, context, and
  cache identities are independently unique.
- [ ] Give the runner a provider callable that raises immediately; prove
  dry-run still returns a manifest, which establishes no invocation without
  asserting on a mock.
- [ ] Prove retryable failures enter `retry_wait` only below
  `max_attempts=3`, the third failure enters `failed`, and a fourth record is
  rejected with `RETRY_LIMIT_EXCEEDED`.
- [ ] Prove an absent production file raises
  `BatchRunnerError.error_code == "QUESTION_SOURCE_NOT_FOUND"`.
- [ ] Prove a synthetic source is accepted only with both the wrapper marker
  and `source_kind=synthetic`.
- [ ] Prove checkpoint JSON round-trip and stale input/version resume
  rejection.
- [ ] Save the exact failing output and command as
  `docs/modules/T07/evidence/day2_red_tests.txt`.

### Task 3: Minimal contract GREEN

**Interfaces**

- Every enum subclasses both `str` and `Enum`.
- Every model subclasses Pydantic `BaseModel` and uses `Field`,
  `field_validator`, or `model_validator`.
- SHA-256 fields match `^[0-9a-f]{64}$`.

- [ ] Implement non-empty and numeric bounds in `app/contracts/batch.py`.
- [ ] Implement cross-field `BatchJob` invariants for attempts, Mock/actual,
  and completed output completeness.
- [ ] Implement embedded identity/version/status consistency in
  `CheckpointRecord`.
- [ ] Implement duplicate/isolation/batch/version consistency in
  `BatchManifest`.
- [ ] Run the contract tests and correct production code only.

### Task 4: Minimal runner GREEN

**Interfaces**

- Stable errors expose `.error_code` and a non-empty string message.
- Canonical input bytes are:

  ```python
  json.dumps(
      record,
      ensure_ascii=False,
      sort_keys=True,
      separators=(",", ":"),
  ).encode("utf-8")
  ```

- [ ] Implement explicit source loading. Production accepts a JSON list;
  synthetic accepts only `{"synthetic": true, "questions": [...]}`.
- [ ] Reject missing sources, wrong source markers, malformed records,
  duplicate IDs, and any count other than 125 with stable error codes.
- [ ] Build paths as `<batch_id>/<question_id>/workspace`, contexts as
  `ctx:<batch_id>:<question_id>:<hash-prefix>`, and caches as
  `cache:<batch_id>:<question_id>:<hash-prefix>`.
- [ ] Keep the provider outside the dry-run path; set route to
  `dry-run/none/none/unassigned` and all budget values to zero.
- [ ] Atomically persist one checkpoint per queued job and the final
  `manifest.json` using same-directory temp files, flush, `fsync`, and
  `os.replace`.
- [ ] Implement failure bookkeeping and compatibility-only resume.
- [ ] Run:

  ```powershell
  & ".\.venv\Scripts\python.exe" -m pytest -q tests/batch
  ```

  Expected GREEN result: all tests in `tests/batch` pass with no
  skip/xfail/warnings.
- [ ] Save exact output as
  `docs/modules/T07/evidence/day2_green_tests.txt`.

### Task 5: CLI and synthetic dry-run

**Interfaces**

- Command:

  ```powershell
  & ".\.venv\Scripts\python.exe" -m scripts.batch_125.dry_run `
    --source tests/batch/fixtures/questions_125.synthetic.json `
    --source-kind synthetic `
    --run-root .pytest_tmp/day2_synthetic `
    --batch-id day2-synthetic
  ```

- Output is one JSON summary containing `batch_id`, `source_kind`,
  `dry_run`, `jobs`, `unique_workspaces`, `unique_context_ids`,
  `unique_cache_namespaces`, `tokens_used`, `actual_results`, and
  `provider_calls`.

- [ ] Implement `argparse` with required explicit source kind and paths.
- [ ] Return exit code 0 only after the manifest and 125 checkpoints are
  written and validated.
- [ ] Run the command against the committed marked-synthetic fixture.
- [ ] Save exact command, exit code, Python version/executable, and JSON
  output as `docs/modules/T07/evidence/day2_synthetic_dry_run.txt`.

### Task 6: Verification

- [ ] Run the exact owner test command and save GREEN evidence.
- [ ] Run:

  ```powershell
  & ".\.venv\Scripts\python.exe" -m pytest -q
  ```

  Save exact collected/pass/fail/skip/warnings/duration and first failure, if
  any, as `docs/modules/T07/evidence/day2_full_tests.txt`.
- [ ] Run `git status -sb`, `git diff --name-only`, `git diff --stat`, and
  `git diff --check`.
- [ ] Confirm every modified/untracked path is within the five T07 owner
  path patterns.
- [ ] Report the authoritative question catalog as the current blocker and
  keep authoritative statistics and historical contamination reproduction as
  not evaluated.
