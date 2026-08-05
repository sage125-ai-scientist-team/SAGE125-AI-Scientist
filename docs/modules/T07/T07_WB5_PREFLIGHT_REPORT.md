# T07-WB5 preflight report

Verification date: 2026-08-06 (Asia/Shanghai)

Freeze ID: `T07-WB5-20260803-v1`

## Decision

`FIVE_REAL_RUNS_BLOCKED`

The only current offline preflight error code is:

`PRICE_SNAPSHOT_REQUIRED`

No actual price snapshot was supplied or validated. No provider preflight or formal five-question run occurred.

## Git and test provenance

- Branch: `t07/b-batch-core`
- Tested code SHA: `7929fed9fccc18160d90fc9cae5949a4a3fd83d4`
- Final docs HEAD: the docs-only commit containing this report; its SHA is
  reported after commit creation in the final PR receipt rather than embedded
  self-referentially
- Integration tip: `73ce7c0731a2aeaaa1b254e8b6d4c1382eab052c`
- Ahead/behind at tested code SHA: `11/0`
- Existing integration merge commit preserved: `76941d072072dfb91fe5eb4faa1e3bdaa9c025f9`
- Python: 3.12.10
- Python executable: `D:\SAGE125-AI-Scientist\.venv\Scripts\python.exe`
- Validation logs were captured under the system temporary directory, outside the repository.

## T01/T03 gates

Old T01 freeze SHA `a4bba2e0b479d5dc0affdf5c2adc4307caed3ec7` is unresolvable (`exit=128`) and is no longer used.

Captain-approved T01 commit: `73ce7c0731a2aeaaa1b254e8b6d4c1382eab052c`.

- Approval reference: `captain_written_approval_confirmed_by_t07_owner`
- Ancestry command exit: 0
- Public interface imported: true
- Public interface callable: true
- Result: `T01_GATE_AVAILABLE`
- T01 owner files changed or copied: none

Tests cover available ancestor, missing SHA, non-ancestor SHA, missing interface, and non-callable interface. No ancestry or interface check was removed.

T03 result: `T03_GATE_AVAILABLE`.

## Price snapshot input contract

- Schema version: `t07.price-snapshot-input.v1`
- Actual price snapshot supplied: false
- Actual price snapshot validated: false
- Existing frozen config remains `price_snapshot=null`
- Runtime target remains the existing `PriceSnapshot.from_mapping()` contract
- Network calls: 0
- Provider calls: 0

The contract freezes exactly six models: `qwen3.6-flash`, `qwen3.7-plus`, `qwen3.7-max`, `qwen-deep-research`, `text-embedding-v4`, and `qwen3-rerank`.

It validates provenance, timezone-aware timestamps, lowercase content hashes, exact model names, plain-string Decimal values, explicit official zero-price provenance, unique price-tier applicability, unsupported fees, currency direction, and frozen FX. Production CLI rejects test-only/synthetic inputs and repository-internal normalized output. Safe output omits all price values and account locators.

Self-check result:

```json
{"actual_price_snapshot_supplied": false, "actual_price_snapshot_validated": false, "decimal_rules_present": true, "fx_rules_present": true, "model_set_matches_frozen_config": true, "provider_calls": 0, "provider_preflight_executed": false, "required_models": 6, "source_provenance_rules_present": true, "spec_schema_valid": true, "timezone_rules_present": true}
```

## Safe provider configuration

- `env_file_exists=true`
- `provider_name=bailian`
- `qwen_configured=true`
- `deep_research_configured=true`
- `configuration_error=None`
- `mock_mode_enabled=false`

The existing configuration loader supplied these booleans. No API key, Workspace ID, `.env`, derived account URL, authorization header, or account balance was printed.

## Tests

| Suite | Collected | Passed | Failed | Skipped | Warnings | Duration | Exit |
|---|---:|---:|---:|---:|---:|---:|---:|
| Price input specification | 36 | 36 | 0 | 0 | 0 | 0.21s | 0 |
| WB5 targeted | 79 | 79 | 0 | 0 | 0 | 0.59s | 0 |
| `tests/batch` | 232 | 230 | 0 | 2 | 0 | 8.03s | 0 |
| Full pytest | 964 | 959 | 1 | 4 | 0 | 59.95s | 1 |

The two batch and two execution skips are Windows symlink-privilege skips. The only latest full-suite failure is outside T07 owner paths:

`tests/test_api_run_modes_and_consistency.py::test_post_runs_real_without_key_returns_400`: expected HTTP 400, actual HTTP 503.

The previous complete run also reproduced the known Streamlit AppTest 30-second timeout (2 failed, 958 passed, 4 skipped, 101.74s). Its isolated rerun passed in 26.23s and the latest complete suite did not reproduce it. No `tests/api` test, timeout, skip, xfail, assertion, or API implementation was changed.

Full pytest regenerated timestamps in two T01 documentation files. Those known test side effects were restored exactly to HEAD and were not committed.

## Final pure-offline WB5 preflight

Command:

`& ".\.venv\Scripts\python.exe" -m scripts.batch_125.preflight_five_real_runs --config docs/modules/T07/run_configs/T07-WB5-20260803-v1.json`

- Exit code: 2
- Status: `FIVE_REAL_RUNS_BLOCKED`
- Error codes: `PRICE_SNAPSHOT_REQUIRED`
- Source provenance: verified
- Five frozen mappings: verified
- Prompt: verified
- Provider configured: true
- T01: `T01_GATE_AVAILABLE`
- T03: `T03_GATE_AVAILABLE`
- Provider calls: 0
- Provider preflight executed: false
- Formal five-question runs: 0

`T01_GATE_VERSION_UNAVAILABLE`, `T01_INTERFACE_UNAVAILABLE`, `PROVIDER_CONFIGURATION_MISSING`, and `GIT_WORKTREE_DIRTY` are not current errors.

## Stop point

- `actual_price_snapshot_supplied=false`
- `actual_price_snapshot_validated=false`
- `provider_calls=0`
- `provider_preflight_executed=false`
- `PRICE_SNAPSHOT_REQUIRED remains active`
- `FIVE_REAL_RUNS_BLOCKED remains active`

The next step requires an operator-supplied, provenance-complete price snapshot that passes the new offline contract. This report does not authorize price lookup, provider preflight, any formal question run, Ready transition, or merge.

## Historical record

Earlier WB5 reports accurately captured old SHA, unavailable T01, missing sources, Prompt mismatch, provider configuration false, and older test totals. Those entries remain historical evidence and are not current provenance.
