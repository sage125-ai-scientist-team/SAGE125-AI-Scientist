# T07-WB5 v2 token-only preflight report

Verification date: 2026-08-07 (Asia/Shanghai)

## Provenance

- Branch: `t07/b-batch-core`
- Tested code SHA: `42b560bf6a2261afc5db1b76aeb2add7194264ca`
- Integration SHA: `f1e2ecd68b075bb8df82992a58397dee71795a60`
- Ahead/behind at tested code SHA: `14/0`
- Python: 3.12.13
- Python executable: `D:\SAGE125-AI-Scientist\.venv\Scripts\python.exe`

The existing venv launcher originally referenced a removed Python 3.12.10
installation. It was repaired in place with the bundled Python 3.12.13 using
`python -m venv --upgrade .venv`; existing site-packages were retained. No
dependency manifest, CI workflow, or PowerShell policy was changed.

## Approved v2 freeze

- Freeze ID: `T07-WB5-20260807-v2`
- Batch schema: `t07.batch.v2`
- Checkpoint schema: `t07.checkpoint.v2`
- Budget policy: `t07.budget.token-only.v2`
- Budget mode: `token_only`
- Captain reference: `captain-option-b-approved-2026-08-07`
- Per-question limit: 200,000 tokens
- Batch limit: 1,000,000 tokens
- Maximum output per call: 8,192 tokens
- Cost accounting required: false
- Price snapshot required: false

The five IDs, complete questions, canonical hashes, source, provider, route,
models, and Prompt identity match the retained v1 freeze.

## Exact validation results

| Check | Result | Duration | Exit |
|---|---|---:|---:|
| v2/legacy targeted tests | 120 passed | 0.85s | 0 |
| `tests/batch` | 248 passed, 2 skipped | 8.47s | 0 |
| Full pytest | 981 passed, 1 failed, 4 skipped | 59.13s | 1 |
| Offline v2 preflight | ready; no errors | 1.9s command wall time | 0 |

The two batch skips and two execution skips are Windows symlink-privilege
checks. The only latest full-suite failure is outside T07 owner paths:

`tests/test_api_run_modes_and_consistency.py::test_post_runs_real_without_key_returns_400`

Expected HTTP 400; actual HTTP 503. The known Streamlit AppTest 30-second
timeout occurred in the preceding full run but did not recur in the latest full
run; its isolated rerun passed (`1 passed`, 26.39s). No API/UI code, timeout,
skip, xfail, or assertion was changed.

Full pytest generated two T01 documentation side effects. They were restored
exactly to HEAD and were not committed.

## Offline preflight decision

- Status: `FIVE_REAL_RUNS_READY_FOR_PROVIDER_PREFLIGHT`
- Error codes: none
- Source provenance: verified
- T01: `T01_GATE_AVAILABLE`
- T03: `T03_GATE_AVAILABLE`
- Provider configured: true
- Qwen configured: true
- Deep research configured: true
- Mock mode: false
- Cost accounting required: false
- Price snapshot required: false
- Provider calls: 0
- Provider preflight executed: false
- Five real runs: 0
- Secret output: none

“Ready for provider preflight” means only that the offline engineering gate is
green under the approved token-only policy. Provider preflight was not run,
the five questions were not run, Day 5 is not declared complete, and this
report does not claim the PR is mergeable.

Costs were not collected under the captain-approved token-only policy. No cost
statistics or fictional zero-cost values were produced. The former 12/125 cost
estimation requirement is waived for this WB5 v2 execution only.
