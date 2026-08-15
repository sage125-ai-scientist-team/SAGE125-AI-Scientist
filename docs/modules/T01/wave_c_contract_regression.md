# T01 Wave C — Contract regression report (NOT human source signoff)

**reviewed_subject_sha:** `344482e481398fd304782b69d62c93f6441c7b6c`

This report is **contract-layer only**. It must **not** be counted as
human original-text verification of live scientific sources.

| suite | machine_passed | classification | notes |
|---|---|---|---|
| Q028-contract-regression | True | contract_layer_not_human_source_signoff | Q028 contract-layer regression only; not a live pipeline trace; excluded from human original-text signoff sample set |

## Reproduce

```powershell
python -c "from app.evidence.q028_regression import run_q028_regression; print(run_q028_regression().to_dict())"
```

