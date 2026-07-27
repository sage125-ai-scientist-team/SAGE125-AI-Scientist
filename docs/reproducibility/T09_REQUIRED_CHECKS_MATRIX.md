# T09 required-check matrix

All checks run on `windows-latest` with Python 3.12, `MOCK_LLM=true`, `PYTHONUTF8=1`, and `PYTHONIOENCODING=utf-8`. The workflow has only `contents: read` permission. Each listed command is a real failing gate: its non-zero exit code fails the job. No check uses `continue-on-error`.

| Job | Command | Inputs and boundary | Failure condition | Evidence |
| --- | --- | --- | --- | --- |
| `lint` | `python -X utf8 scripts/eval/wave_a_quality.py lint` | Owned Python files under `scripts/eval` and `tests/integration`; no network or secrets. | Syntax error or trailing whitespace. | Actions log; local run: exit 0, 3 files, no failures. |
| `type` | `python -X utf8 scripts/eval/wave_a_quality.py type` | The same owned paths; no network or secrets. | A public function lacks an argument or return annotation. | Actions log; local run: exit 0, no failures. |
| `unit` | `python -X utf8 -m pytest -q --ignore=tests/integration` | Offline project suite with the integration fixture excluded; `MOCK_LLM=true`. | Any collection error, test failure, or command error. | Actions log; local run: 272 passed, exit 0. |
| `integration` | `python -X utf8 -m pytest -q tests/integration` | Deterministic Wave A fixture; benchmark files are created below pytest's temporary directory. | Any fixture, dry-run, or schema-validation failure. | Actions log; local run: 1 passed, exit 0. |
| `security` | `python -X utf8 scripts/audit_project.py` | Repository source and ignored local outputs only; no production credentials are supplied. | Any audit critical finding. | Actions log; local run: `critical=0`, `warnings=0`, exit 0. |
| `build` | `python -X utf8 -m compileall -q app scripts/eval`; `python -X utf8 scripts/eval/benchmark_skeleton.py --dry-run --output "${{ runner.temp }}/benchmark.json"`; `python -X utf8 scripts/eval/wave_a_quality.py validate-result --result "${{ runner.temp }}/benchmark.json"` | Python source plus a planned-only benchmark manifest in the runner temporary directory. | Compile error, dry-run failure, malformed manifest/CSV, or a measured score in a dry-run. | Actions log; local run: all three commands exit 0. |

## Trigger and review contract

The workflow triggers for pushes and for pull requests to `integration/2026-08-10` with the events `opened`, `synchronize`, `reopened`, and `edited`. The stable job names above are required-check candidates. Repository branch-protection settings are intentionally outside this PR's scope.

The current local runs are evidence of the commands, not GitHub Actions results. After the normal non-force push, the PR must show all six jobs with their GitHub Actions links before captain approval is requested. Until then, the PR stays Draft.
