# T09 quality baseline

## Provenance and separation of evidence

| Field | Value |
| --- | --- |
| Integration baseline | `1642ea05e88b853f18d24739d9d2134c3448eb7b` |
| CI implementation commit | `44cec54b7993aca850230c72a16510bf79009774` |
| Evidence-document commit | Recorded separately after this document is committed to avoid a self-referential SHA cycle. |
| Tested source tree | Clean detached worktree at `a0d3f2a244c9f11d346328a782dec4e4cb0cc8db`; the testable source is unchanged by the later CI/evidence-only remediation. |
| Interpreter | `D:\AI-Projects\SAGE125-AI-Scientist\.venv\Scripts\python.exe`, Python 3.12.10 |
| Operating system | Windows 11, 10.0.26200.8875 |
| Environment | `MOCK_LLM=true`, `PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8`; no `.env`, private question list, or local PDF. |

GitHub Actions is separate evidence. At this writing no GitHub check, run URL, or artifact URL is asserted as successful for the new implementation commit.

## Exact clean-worktree commands and results

```powershell
$env:MOCK_LLM='true'
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
$py = 'D:\AI-Projects\SAGE125-AI-Scientist\.venv\Scripts\python.exe'
```

| Check | Exact command | Exit | Collected | Passed | Failed | Skipped | Warnings | Generated artifact |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| interpreter | `& $py -X utf8 -c "import sys, platform; print(sys.executable); print(sys.version); print(platform.platform())"` | 0 | n/a | n/a | 0 | n/a | none | version/platform output |
| lint | `& $py -X utf8 scripts/eval/wave_a_quality.py lint` | 0 | 3 owned files | n/a | 0 | n/a | none | `lint-result.json` in temporary evidence directory |
| type | `& $py -X utf8 scripts/eval/wave_a_quality.py type` | 0 | n/a | n/a | 0 | n/a | none | `type-result.json` in temporary evidence directory |
| unit | `& $py -X utf8 -m pytest -q --ignore=tests/integration --junitxml $evidenceRoot\unit-junit.xml` | 0 | 272 | 237 | 0 | 35 | none | `unit-junit.xml` |
| integration | `& $py -X utf8 -m pytest -q tests/integration --junitxml $evidenceRoot\integration-junit.xml` | 0 | 1 | 1 | 0 | 0 | none | `integration-junit.xml` |
| security | `& $py -X utf8 scripts/audit_project.py` | 0 | n/a | `critical=0` | 0 | n/a | `warnings=1` | `exports/audit/audit_report.{json,md}` |
| build compile | `& $py -X utf8 -m compileall -q app scripts/eval` | 0 | n/a | completed | 0 | n/a | none | none |
| build dry-run | `& $py -X utf8 scripts/eval/benchmark_skeleton.py --dry-run --output $evidenceRoot\benchmark.json` | 0 | 5 planned variants | completed | 0 | n/a | none | `benchmark.{json,csv}` |
| build schema | `& $py -X utf8 scripts/eval/wave_a_quality.py validate-result --result $evidenceRoot\benchmark.json` | 0 | JSON and CSV | completed | 0 | n/a | none | validated manifest |
| full pytest | `& $py -X utf8 -m pytest -q` | 0 | 273 | 238 | 0 | 35 | none | pytest console result |

`$evidenceRoot` was `C:\Users\rockk\AppData\Local\Temp\sage125-t09-clean-evidence`; it is outside the repository and is not committed. The clean worktree did not contain `questions_125.json` or `data/raw/sjtu-booklet.pdf`. The 35 skips are the named input-gated tests for those absent private inputs. There were no failed test names in this run.

## Remote status

The normal push of `44cec54` and the later evidence-document commit must create the workflow run. Only then may this document be supplemented with the six actual GitHub statuses, run URL, and artifact URLs. Pending, queued, skipped, or approval-required states are not represented as passing.
