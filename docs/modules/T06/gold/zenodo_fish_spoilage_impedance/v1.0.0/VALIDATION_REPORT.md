# VALIDATION_REPORT — zenodo_fish_spoilage_impedance v1.0.0

## Interpreter

- Path: `D:\ZBY\software\Anaconda\envs\sage125\python.exe`
- Environment: conda `sage125`

## Commands run

1. `python docs/modules/T06/gold/zenodo_fish_spoilage_impedance/v1.0.0/fetch_and_verify.py --validate`
   - Exit: 0
   - Result: PASS (15 files checked, 100 gold labels, modalities table+chart)

2. `python docs/modules/T06/gold/zenodo_fish_spoilage_impedance/v1.0.0/fetch_and_verify.py --fetch --workdir %TEMP%\t06-gold-repro-run`
   - Exit: 0
   - Elapsed: ~5.2s
   - Result: Re-downloaded Zenodo bytes matched frozen SHA-256 for all five primary science files

3. `python -m compileall -q app tests`
   - Exit: 0

4. `python -m pytest -q tests/multimodal`
   - Exit: 0
   - Result: 29 passed

5. `python -m pytest -q`
   - Exit: 0
   - Result: **683 passed, 38 skipped** in ~76.7s

6. `git diff --check`
   - Exit: 0

## Source hashes (primary science files)

| File | SHA-256 |
|------|---------|
| raw/fishtrial_resistance.csv | 86b01101eb00e72ab67413742adeb0fb2396cbb3bfb00e93909e7446b560f919 |
| raw/fishtrial_capacitance.csv | 806406cc5d42930916e148dff17cb21a472a5a975edd2aec15cdd03df2b0cd5b |
| raw/fishtrial_realz.csv | 8130c9ce98f4fc9926e846b72fc0e78e98224c89ff04c3da4d54144f10c77d40 |
| raw/fishtrial_imagz.csv | 42d81e397b1ac8db6a35341e37224847479c2de06ef7e8b12082aa295294ede4 |
| raw/Picture1.png | 8297ce9a09b70cc74fcb4566b643fecd7b447edfbf9cbb6517898e925430706a |

## License

- CC-BY-4.0 confirmed via Zenodo API JSON (`license.id=cc-by-4.0`) and landing HTML snapshot.

## Fail-closed checks exercised

- Hash mismatch → non-zero exit (unit test)
- Synthetic flag → loader raises
- Chart relative tolerance 5% rejects 6% error

## Status

`SOURCE_FETCH_VERIFY=PASS`
