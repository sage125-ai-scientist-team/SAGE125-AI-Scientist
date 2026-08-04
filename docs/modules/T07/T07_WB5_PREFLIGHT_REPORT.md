# T07-WB5 preflight report

Verification date: 2026-08-05 (Asia/Shanghai)

Freeze ID: `T07-WB5-20260803-v1`

## Decision

`FIVE_REAL_RUNS_BLOCKED`

Current offline blockers:

- `PROVIDER_CONFIGURATION_MISSING`
- `PRICE_SNAPSHOT_REQUIRED`
- `T01_GATE_VERSION_UNAVAILABLE`

`PROVIDER_PREFLIGHT_NOT_EXECUTED`

No provider request and no formal five-question run occurred. Provider calls are 0. PR #31 was verified `OPEN`, `Draft=true`, base `integration/2026-08-10`, and remains Draft.

## Git and environment provenance

- Branch: `t07/b-batch-core`
- Tested code SHA: `4560d0fd89a658e14eaeaedb2dcf10e3be82f5fc`
- Integration SHA: `9dc00a8e3fbd8305976147b8df6a7a54fb0ba00c`
- Ahead/behind against integration: `8/0`
- Merge required: no; latest fetched integration was already an ancestor
- Merge in progress: no
- Python: 3.12.10
- Python executable: `D:\SAGE125-AI-Scientist\.venv\Scripts\python.exe`
- `pip check`: `No broken requirements found.`

The `.venv` is operational again because its configured Python 3.12.10 installation is present. No dependency file, lock file, CI workflow, `.env`, or PowerShell execution policy was changed, and no environment replacement was needed.

The PR head repository reported by GitHub is `myr-111/SAGE125-AI-Scientist-fork`; the local `origin` correctly points to that repository. The non-`-fork` origin stated in the supplied runbook is stale and was not substituted because it would not update PR #31.

## Authoritative source verification

| Source | Actual size | SHA-256 | Result |
|---|---:|---|---|
| `data/raw/sjtu-booklet.pdf` | 8,422,081 | `4bda50e8e3c90f8968f1bfd72ded4d9587ae80cd40ba66656a12c93abcf8e576` | verified |
| `data/processed/questions_125.json` | 105,068 | `b6712a3b53f9776d7f695ea67f810c30b7d97ee59c183009432870d3224cdebb` | verified; UTF-8 without BOM |
| `data/processed/extraction_report.md` | 1,748 | `f895cbbd2c3e394040e0068c7c48d6ec35ad43c1c33b84b915d623f73cfbeb27` | verified; count/status/quality PASS |

JSON audit: total 125, unique IDs 125, exact range `Q001`-`Q125`, empty IDs 0, empty questions 0. All inputs remain Git-ignored and untracked. Synthetic fallback was not used.

The PDF is provenance/background, not scientific literature evidence for the eventual answers.

## Frozen five-question mapping

Mapping uses `question_id = record["id"]` and the existing T07 canonical-input function.

| ID | Page | Domain | Complete question | Canonical input hash |
|---|---:|---|---|---|
| `Q001` | 7 | Mathematical Sciences | What makes prime numbers so special? | `310bf14faa04574681fb726cba14f7f12487d8881333b2086a35afdfffc0dc6d` |
| `Q028` | 15 | Biology | Will it be possible to cure all cancers? | `badcae2fec281a0bbaec81b36d8ed4a149696db855d0f399e7cbe382fdc78da8` |
| `Q050` | 21 | Astronomy | When will the universe die? Will it continue to expand? | `6f5c2f81f71800c2d3c449231ddfdb8816fd0e3ed1d53f1db1605c7afd118222` |
| `Q075` | 27 | Physics | What are the smallest building blocks of matter? | `f3f914199353942d7abf4709ffbfe67c6ae8fb8b8cba905dea0cc7f316b8c0eb` |
| `Q107` | 37 | Ecology | Can we stop global climate change? | `3448280c074284d4c316a8c013df63fb1c66d71c8a151fb4d4d1be119d2713b9` |

All five authoritative records include `source_page` and a non-empty `booklet_excerpt`; those fields are bound by each complete-record canonical hash.

## Prompt and schema verification

- Prompt version: `sage125-agent-prompts-20260803-v1`
- Amendment: `2026-08-04 captain normalization amendment`
- Hash mode: `utf8_lf_normalized_text_sha256`
- Verified SHA-256: `fa2d1da7d40ad6a6da800d6a41484973b46b63ebe72ed48da44b437644a5c808`
- `app/agents/prompts.py` modified: no
- Four frozen shared schema files: verified by their recorded raw byte size/SHA-256

Tests prove CRLF, CR, and LF Prompt line endings produce the same normalized hash while other text remains significant.

## Safe provider diagnostics

- `env_file_exists=true`
- `provider_name=bailian`
- `qwen_configured=false`
- `deep_research_configured=false`
- `mock_mode_enabled=false`
- `config_loader_invoked=true`

The CLI now invokes the existing repository configuration loader but emits only these safe booleans/name. It never prints `.env`, an API key, or an authorization header.

## T01/T03 and price gates

- Approved T01 commit: `a4bba2e0b479d5dc0affdf5c2adc4307caed3ec7`
- T01: unavailable; `git merge-base --is-ancestor` fails, so `T01_GATE_VERSION_UNAVAILABLE` remains. No T01 code was copied or cherry-picked.
- T03: `T03_GATE_AVAILABLE`.
- Price snapshot: absent; `PRICE_SNAPSHOT_REQUIRED` remains. Unknown cost was not treated as zero.

## Tests

| Suite | Collected | Passed | Failed | Skipped | Warnings | Duration | Exit |
|---|---:|---:|---:|---:|---:|---:|---:|
| WB5 targeted | 40 | 40 | 0 | 0 | 0 | 0.61s | 0 |
| `tests/batch` | 193 | 191 | 0 | 2 | 0 | 9.54s | 0 |
| Full pytest | 858 | 853 | 1 | 4 | 0 | 64.03s | 1 |

The two batch skips and two execution skips are Windows symlink-privilege skips. The current full-suite failure is:

`tests/test_api_run_modes_and_consistency.py::test_post_runs_real_without_key_returns_400`: expected HTTP 400, actual HTTP 503.

That test and the corresponding API implementation are outside T07 owner paths and were not changed.

Historical Streamlit note: an earlier full run in this verification round reproduced the known 30-second Streamlit AppTest timeout and also had the API failure (2 failed, 852 passed, 4 skipped, 108.86s). The isolated Streamlit rerun passed in 26.22s and the latest complete run did not reproduce it. No `tests/api` test, timeout, skip, xfail, or assertion was modified, and this report does not claim a T07 code fix resolved that transient timeout.

Historical environment and initial collection RED results remain preserved in `docs/modules/T07/evidence/wb5_preflight_red_tests.txt` and are not current.

## Final pure-offline preflight

Command:

`& ".\.venv\Scripts\python.exe" -m scripts.batch_125.preflight_five_real_runs --config docs\modules\T07\run_configs\T07-WB5-20260803-v1.json`

- Exit code: 2 (fail-closed)
- Status: `FIVE_REAL_RUNS_BLOCKED`
- Source provenance verified: true
- Five mappings verified: true
- Prompt verified: true
- Error codes: `PROVIDER_CONFIGURATION_MISSING`, `PRICE_SNAPSHOT_REQUIRED`, `T01_GATE_VERSION_UNAVAILABLE`
- T03: `T03_GATE_AVAILABLE`
- Provider calls: 0
- Provider preflight executed: false
- Formal five-question runs: 0

`SOURCE_MISSING`, `FROZEN_QUESTION_NOT_EVALUATED`, `CODE_FILE_SHA256_MISMATCH`, `PROMPT_HASH_MISMATCH`, and `GIT_WORKTREE_DIRTY` are no longer current codes.

## Current blockers and handoff

1. Captain-approved T01 commit/interface must become available on the integration ancestry.
2. Operator must supply an approved provider price snapshot.
3. Bailian/Qwen configuration is currently incomplete according to the existing loader.
4. Captain authorization is required before provider preflight or any of the five formal questions.
5. The non-T07 API 400/503 full-suite failure requires its owner.

PR #31 must remain Draft. No provider flag, real Bailian call, formal five-question run, Ready transition, merge, rebase, force push, or new PR is authorized by this report.

## Historical 2026-08-03 state

The earlier report accurately recorded absent PDF/JSON, unevaluated mappings, raw Prompt hash mismatch, old test counts, and an uncommitted dirty worktree. Those values are retained here as history only and must not be used as current provenance.
