# T09 required-check matrix

The workflow runs on `windows-latest` with Python 3.12, `MOCK_LLM=true`, `PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8`, and `contents: read` only. Pull requests to `integration/2026-08-10` trigger for `opened`, `synchronize`, `reopened`, `edited`, and `ready_for_review`.

Every Python command uses `python -X utf8`. A non-zero command exit fails its job. `if: always()` is used only on evidence upload steps so a failing command retains its generated diagnostic; missing expected evidence fails the upload (`if-no-files-found: error`).

| Job ID | Exact command(s) | Input and failure condition | Generated output / artifact | GitHub evidence |
| --- | --- | --- | --- | --- |
| `lint` | `python -X utf8 scripts/eval/wave_a_quality.py lint > "${{ runner.temp }}/lint-result.json"` | Owned eval/integration Python files; fails on syntax or trailing whitespace. | `lint-result.json` / `t09-lint-result` | Job log and artifact on the run. |
| `type` | `python -X utf8 scripts/eval/wave_a_quality.py type > "${{ runner.temp }}/type-result.json"` | Same owned paths; fails on missing public parameter or return annotations. | `type-result.json` / `t09-type-result` | Job log and artifact on the run. |
| `unit` | `python -X utf8 -m pytest -q --ignore=tests/integration --junitxml "${{ runner.temp }}/unit-junit.xml"` | Offline suite; fails on collection or test failure. | `unit-junit.xml` / `t09-unit-junit` | Job log and artifact on the run. |
| `integration` | `python -X utf8 -m pytest -q tests/integration --junitxml "${{ runner.temp }}/integration-junit.xml"` | Wave A fixture; fails on fixture, dry-run, or schema failure. | `integration-junit.xml` / `t09-integration-junit` | Job log and artifact on the run. |
| `security` | `python -X utf8 scripts/audit_project.py` | Repository audit; fails on any critical finding. | `exports/audit/audit_report.{json,md}` / `t09-security-audit` | Job log and artifact on the run. |
| `build` | `python -X utf8 -m compileall -q app scripts/eval`; `python -X utf8 scripts/eval/benchmark_skeleton.py --dry-run --output "${{ runner.temp }}/benchmark.json"`; `python -X utf8 scripts/eval/wave_a_quality.py validate-result --result "${{ runner.temp }}/benchmark.json"` | Source plus planned-only manifest; fails on compile, schema, or dry-run score violation. | `benchmark.{json,csv}` / `t09-build-benchmark` | Job log and artifact on the run. |

Local execution is documented separately from GitHub Actions. The Actions columns are locations, not assertions that a remote run has passed; run URLs and statuses are filled only after GitHub creates them for the current head.
