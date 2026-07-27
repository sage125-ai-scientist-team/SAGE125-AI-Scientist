# T09 quality baseline

## Provenance

| Field | Value |
| --- | --- |
| Integration baseline | `upstream/integration/2026-08-10` at `1642ea05e88b853f18d24739d9d2134c3448eb7b` |
| Tested PR candidate | `013f9c843c1347ce8f9b32fab7cdcf0a53e67485` |
| Branch | `t09/a-quality-contract` |
| Recorded | 2026-07-28T04:18:19+08:00 |
| Interpreter | `.venv\Scripts\python.exe`, Python 3.12.10 |
| Operating system | Microsoft Windows 10.0.26200.8875 |
| Mode | Offline: `MOCK_LLM=true`; no `.env` was loaded and no live model was invoked. |

The tested candidate is the merge result containing the latest integration baseline and the final CI conflict resolution. Subsequent documentation-only evidence edits do not change the tested executable code.

## Exact execution environment

```powershell
$env:MOCK_LLM='true'
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
$py = '.venv\Scripts\python.exe'
```

## Results from one local verification run

| Check | Exact command | Exit | Collected | Passed | Failed | Skipped | Warnings |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| lint | `& $py -X utf8 scripts/eval/wave_a_quality.py lint` | 0 | 3 owned files | n/a | 0 | n/a | none reported |
| type | `& $py -X utf8 scripts/eval/wave_a_quality.py type` | 0 | n/a | n/a | 0 | n/a | none reported |
| unit | `& $py -X utf8 -m pytest -q --ignore=tests/integration` | 0 | 272 | 272 | 0 | 0 | none reported |
| integration | `& $py -X utf8 -m pytest -q tests/integration` | 0 | 1 | 1 | 0 | 0 | none reported |
| security | `& $py -X utf8 scripts/audit_project.py` | 0 | n/a | `critical=0` | 0 | n/a | `warnings=0` |
| build: compile | `& $py -X utf8 -m compileall -q app scripts/eval` | 0 | n/a | completed | 0 | n/a | none reported |
| build: dry-run | `& $py -X utf8 scripts/eval/benchmark_skeleton.py --dry-run --output $benchmark` | 0 | 5 planned variants | completed | 0 | n/a | none reported |
| build: schema | `& $py -X utf8 scripts/eval/wave_a_quality.py validate-result --result $benchmark` | 0 | JSON and CSV | completed | 0 | n/a | none reported |
| full pytest | `& $py -X utf8 -m pytest -q` | 0 | 273 | 273 | 0 | 0 | none reported |

`$benchmark` was a unique path beneath the system temporary directory: `C:\Users\rockk\AppData\Local\Temp\sage125-t09-benchmark-9b2acaae-4e5d-4713-8e06-72fc96d170b0\benchmark.json`. Its JSON and companion CSV are planned-only dry-run evidence and are not repository artifacts.

## Failures

There were no failed tests, skipped tests, or non-zero commands in this run. Consequently there are no failing test names or failure reasons to report. This statement applies only to the exact run and candidate SHA above; it does not claim a GitHub Actions result.

## Remote verification status

The six configured GitHub Actions jobs have not yet been observed on the post-fix head. Their status and run URLs must be recorded from GitHub after a normal push; they are not pre-filled as passing in this baseline.
