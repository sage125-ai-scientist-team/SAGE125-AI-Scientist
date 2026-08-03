# VALIDATION_REPORT — zenodo_fish_spoilage_impedance v1.0.0

## Interpreter

- Path: `D:\ZBY\software\Anaconda\envs\sage125\python.exe`
- Version: Python 3.11.15
- Environment: conda `sage125`

## Commands run on final remediation package (re-executed; not copied from older reports)

1. `python -B docs/modules/T06/gold/zenodo_fish_spoilage_impedance/v1.0.0/fetch_and_verify.py --validate`
   - Workdir: repository root
   - Exit: 0
   - Result: PASS (`files_checked=18`, `gold_labels=100`, modalities table+chart)
   - Network used: NO

2. Isolated fetch #1 (unique empty temp dir via `tempfile.mkdtemp(prefix='sage125-t06-fetch-')`)
   - Command: `python -B -c "import subprocess,sys,tempfile; from pathlib import Path; w=Path(tempfile.mkdtemp(prefix='sage125-t06-fetch-')); raise SystemExit(subprocess.call([sys.executable,'-B','docs/modules/T06/gold/zenodo_fish_spoilage_impedance/v1.0.0/fetch_and_verify.py','--fetch','--workdir',str(w)]))"`
   - Exit: 0
   - Cache/fixture/synthetic fallback: NO

3. Isolated fetch #2 (second independent empty temp dir; same command form)
   - Exit: 0
   - Tree digest equal to fetch #1: YES
   - Repository worktree unchanged: YES

4. `python -m compileall -q app tests docs/modules/T06/gold/zenodo_fish_spoilage_impedance/v1.0.0/fetch_and_verify.py`
   - Exit: 0

5. `python -B -m pytest -q tests/multimodal/test_real_gold_provenance.py`
   - Exit: 0
   - Result: **13 passed**

6. `python -B -m pytest -q tests/multimodal`
   - Exit: 0
   - Result: **31 passed**

7. `python -B -m pytest -q`
   - Exit: 0
   - Result: **685 passed, 38 skipped** in ~62.8s
   - Skips are pre-existing missing local fixtures (`questions_125.json` / PDF), not provenance required skips

8. `python -X utf8 scripts/eval/wave_a_quality.py lint`
   - Exit: 0
   - Result: `{"check":"wave_a_lint","files":3,"failures":[]}`

9. `python -X utf8 scripts/eval/wave_a_quality.py type`
   - Exit: 0
   - Result: `{"check":"wave_a_type_contract","failures":[]}`

10. `git diff --check` on staged remediation paths
    - Exit: 0

## Inventory

- `SHA256SUMS` hashed file count: **18** (does not list itself)
- Package also tracks `.gitattributes` outside `SHA256SUMS` (EOL/binary policy)

## Source hashes (Zenodo science files)

| File | SHA-256 |
|------|---------|
| raw/fishtrial_resistance.csv | 86b01101eb00e72ab67413742adeb0fb2396cbb3bfb00e93909e7446b560f919 |
| raw/fishtrial_capacitance.csv | 806406cc5d42930916e148dff17cb21a472a5a975edd2aec15cdd03df2b0cd5b |
| raw/fishtrial_realz.csv | 8130c9ce98f4fc9926e846b72fc0e78e98224c89ff04c3da4d54144f10c77d40 |
| raw/fishtrial_imagz.csv | 42d81e397b1ac8db6a35341e37224847479c2de06ef7e8b12082aa295294ede4 |
| raw/Picture1.png | 8297ce9a09b70cc74fcb4566b643fecd7b447edfbf9cbb6517898e925430706a |

## License

- CC-BY-4.0 confirmed via Zenodo API JSON (`license.id=cc-by-4.0`) and landing HTML snapshot.
- Zenodo source scope vs team packaging scope documented in `manifest.json` / `source_metadata.json` / `README.md`.

## Fail-closed checks exercised

- Raw byte change → non-zero validate exit
- Derived newline change → non-zero validate exit
- Duplicate SHA256SUMS path → non-zero validate exit
- Synthetic flag → loader raises
- Chart relative tolerance 5% rejects 6% error; zero absolute tolerance 0.0; `EPS_USED=NO`

## Placeholder scan (formal package texts)

- Confirmation-pending token occurrences: 0
- Angle-bracket template tokens and fill-me markers: 0
- Explained JSON nulls only in table gold labels for chart-only fields (`bbox` / `series_id` / `coordinate_system`)

## Status

`SOURCE_FETCH_VALIDATE=PASS`
Final accept-candidate request is decided only after final Head CI succeeds (see PR description / handoff).
