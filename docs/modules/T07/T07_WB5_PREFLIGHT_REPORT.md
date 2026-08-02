# T07-WB5 preflight report

Date: 2026-08-03 (Asia/Shanghai)

Freeze ID: `T07-WB5-20260803-v1`

## Decision

`FIVE_REAL_RUNS_BLOCKED`

`T01_GATE_VERSION_UNAVAILABLE`

`PROVIDER_PREFLIGHT_NOT_EXECUTED`

No provider request and no formal five-question run occurred. PR #31 was verified OPEN and Draft before implementation and was not modified.

## Git and test provenance

- Branch: `t07/b-batch-core`
- Tested code SHA: `20354d62c54cb78e50e2f672e292ffd72d548b73`
- Origin branch SHA: `20354d62c54cb78e50e2f672e292ffd72d548b73`
- Integration SHA: `9dc00a8e3fbd8305976147b8df6a7a54fb0ba00c`
- Ahead/behind against integration: `4/0`
- Merge in progress: no
- Worktree at the start: clean
- Worktree during final offline preflight: dirty by design because this WB5 implementation is uncommitted; formal preflight correctly returned `GIT_WORKTREE_DIRTY`

The latest operator-confirmed full-suite run used `.venv\Scripts\python.exe` directly with `pytest -q -rs` and completed successfully. The earlier environment RED and initial collection RED remain preserved in `wb5_preflight_red_tests.txt` as historical pre-implementation evidence; they are not current full-suite results.

## Frozen configuration

- Provider: `bailian`
- Route: `t07-wb5-bailian-qwen-stack-v1`
- Models: `qwen3.6-flash`, `qwen3.7-plus`, `qwen3.7-max`, `qwen-deep-research`, `text-embedding-v4`, `qwen3-rerank`
- Model version: `qwen-stack-20260803-v1`
- Prompt version: `sage125-agent-prompts-20260803-v1`
- Batch/checkpoint schemas: `t07.batch.v1` / `t07.checkpoint.v1`
- Per-question budget: 200,000 tokens and USD 3.00
- Batch budget: 1,000,000 tokens and USD 15.00
- Maximum output per call: 8,192 tokens
- Frozen budget error: `BUDGET_EXHAUSTED`
- Approved T01 commit: `a4bba2e0b479d5dc0affdf5c2adc4307caed3ec7`

No API key or Secret appears in the freeze or report.

## Authoritative source verification

| Source | Expected size | Expected SHA-256 | Actual result |
|---|---:|---|---|
| `data/raw/sjtu-booklet.pdf` | 8,422,081 | `4bda50e8e3c90f8968f1bfd72ded4d9587ae80cd40ba66656a12c93abcf8e576` | `SOURCE_MISSING` |
| `data/processed/questions_125.json` | 105,068 | `b6712a3b53f9776d7f695ea67f810c30b7d97ee59c183009432870d3224cdebb` | `SOURCE_MISSING` |

The implementation requires exactly 125 JSON records, unique non-empty IDs, lookup by `record["id"]`, all five frozen IDs, exact domain/question matches, and canonical JSON hashes. It rejects synthetic sources and never falls back to fixtures.

Because the production JSON is absent, the five mappings are truthfully `not evaluated`:

| Question ID | Domain | Complete question | Canonical input hash |
|---|---|---|---|
| `Q001` | not evaluated | not evaluated | not evaluated |
| `Q028` | not evaluated | not evaluated | not evaluated |
| `Q050` | not evaluated | not evaluated | not evaluated |
| `Q075` | not evaluated | not evaluated | not evaluated |
| `Q107` | not evaluated | not evaluated | not evaluated |

No question text, domain, order, or input hash was guessed.

## Prompt and schema verification

The frozen prompt SHA-256 is `b1afe045af8233f6255e4e1f2dc22645f88a0bae6ebf26b89028b3f2b383c3e0`; the current `app/agents/prompts.py` SHA-256 is `fa2d1da7d40ad6a6da800d6a41484973b46b63ebe72ed48da44b437644a5c808`. Offline preflight correctly returned `CODE_FILE_SHA256_MISMATCH`.

All four selected schema files matched their recorded current size and SHA-256:

| Path | Size | SHA-256 |
|---|---:|---|
| `app/core/schemas.py` | 15,743 | `eece52a348093213aad134642a5f9dd611d6ebaa560a9259f93beea8e9c670f5` |
| `app/core/agent_schemas.py` | 12,951 | `216204b1325439e6b55fb0fb73955dd6584a22d8a2853a120ef805bfda37605b` |
| `app/contracts/evidence.py` | 9,467 | `d954ae5d023faf67b2aa564113e12a57ccee45b338633fc7d21e16a5887cd7c9` |
| `app/contracts/validation.py` | 44,304 | `961cfbdbbd291315cc62e51931d38f060a0cac911ac468a27e86444e98c49152` |

Static prompt-file SHA and per-call dynamic prompt SHA are distinct audit fields.

## T01/T03 availability

T01 is blocked. `git cat-file` and `git merge-base --is-ancestor` could not resolve the approved commit in this checkout, and `app.evidence.precheck_bundle_for_validation` is absent. The stable result is `T01_GATE_VERSION_UNAVAILABLE`; no cherry-pick, copy, empty gate, or fabricated pass was used.

T03 is available. The implementation verified and uses:

- `ValidationContext.model_validate`
- `GateResult.from_legacy`
- `ValidationReport.from_context`
- `run_all_quality_gates`

## Completion-gate flow

Every formal question enters `gates_pending`. `evaluate_question_completion` derives the only `completed` decision from these 20 conditions:

1. Verified production source provenance.
2. Exact frozen question/domain/input mapping.
3. Batch ID.
4. Question ID.
5. Complete question text.
6. Domain.
7. Run ID.
8. Canonical version ID.
9. Source hash.
10. Input hash.
11. A freshly rebuilt `ValidationContext` with both actual-execution flags true.
12. T01 public evidence precheck passes.
13. Every T03 quality gate passes after `GateResult.from_legacy` conversion.
14. No open P0/P1.
15. All five base artifacts exist in the manifest.
16. `llm_call_audit.json` exists in the manifest.
17. Call audit is non-fallback and has known accounted cost.
18. Manifest identity, checksum, and call-audit hash match.
19. Delivery-index checksum and per-artifact hashes match the manifest.
20. Per-question and batch budgets both pass.

`build_actual_validation_context` calls the real T03 model validator and rejects false or mismatched actual-execution values. It never calls a mock context builder. T01/T03 import failures become blocking P1 gates. The five base artifacts remain unchanged; `build_artifact_manifest` accepts only the separately frozen `llm_call_audit.json` as a supplemental file, validates it, and allows its record to flow into the delivery index.

`save_completion_gate_result` persists the exact `validation_report.json`, `gate_results.json`, and 20-condition `completion_gate.json` as UTF-8 question-scoped artifacts; it never recomputes or upgrades a blocked decision while saving.

The call ledger uses `Decimal`, charges retries and provider preflight, checks the next call before execution, deduplicates resume by sanitized request ID, rejects ID collisions, rejects unknown cost, and never raises frozen limits automatically. Price calculations require an injected snapshot with version, source, and acquisition time.

## Offline CLI result

Command: `python -m scripts.batch_125.preflight_five_real_runs`

Exit code: 2 (expected fail-closed result)

Result status: `FIVE_REAL_RUNS_BLOCKED`

Observed codes:

- `SOURCE_MISSING` for both authoritative files
- `FROZEN_QUESTION_NOT_EVALUATED` for all five IDs
- `CODE_FILE_SHA256_MISMATCH` for the prompt
- `GIT_WORKTREE_DIRTY`
- `PROVIDER_CONFIGURATION_MISSING` (boolean false; no value inspected or emitted)
- `PRICE_SNAPSHOT_REQUIRED`
- `T01_GATE_VERSION_UNAVAILABLE`

T03: `T03_GATE_AVAILABLE`

Provider preflight executed: no (`provider_preflight_executed=false`).

The CLI defaults to offline. Only `--execute-provider-preflight` can permit one eight-token Bailian request, and even then only after every offline gate passes, `MOCK_LLM` is off, an operator price snapshot is supplied, and the audit target is outside the repository. That flag was not executed in this work.

## Tests

RED:

- Requested `.venv` invocation: exit 101; suite not executed because the venv interpreter target is missing.
- Read-only fallback before implementation: exit 2, zero collected, four collection errors, two cache warnings, 0.87s.
- First error: `ModuleNotFoundError: No module named 'app.batch.five_run_preflight'`.

Final:

| Suite | Collected | Passed | Failed | Skipped | Warnings | Duration | Exit |
|---|---:|---:|---:|---:|---:|---:|---:|
| WB5 targeted | 38 | 38 | 0 | 0 | 0 | 0.56s | 0 |
| `tests/batch` | 191 | 189 | 0 | 2 | 0 | 6.94s | 0 |
| Full pytest | 856 | 817 | 0 | 39 | not reported | 61.04s | 0 |

The two batch skips are Windows symlink-privilege skips. The 39 full-suite skips remain recorded as skips and primarily reflect missing authoritative PDF/question inputs plus unavailable Windows symlink privilege.

Historical full-suite note: an earlier attempt reported one transient Streamlit `AppTest` timeout after 30 seconds. The timeout did not reproduce in the latest complete rerun. No `tests/api` or T08 test, timeout, skip, xfail, or assertion was modified, and this report does not claim that a code change fixed the transient timeout. It is not a current blocker.

## Current blockers

1. Authoritative PDF absent.
2. Production 125-question JSON absent.
3. Five domain/question/hash mappings therefore not evaluated.
4. Approved T01 commit not available/proven in HEAD and T01 public bridge absent.
5. Frozen prompt SHA does not match the current prompt file.
6. Provider configuration boolean false in the offline process.
7. Operator price snapshot not supplied.
8. Worktree remains dirty until an authorized human commits the reviewed changes.

## Suggested commit split (not executed)

1. `test(t07): add WB5 fail-closed red and contract coverage`
2. `feat(t07): add frozen five-run preflight, completion gate, and call audit`
3. `docs(t07): record WB5 freeze, evidence, and blocked preflight status`

No commit, push, PR update, Ready transition, merge, provider call, five-question run, or T01 cherry-pick was performed.
