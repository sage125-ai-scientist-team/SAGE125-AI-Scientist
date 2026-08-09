# T06 Real Gold Package — zenodo_fish_spoilage_impedance / v1.0.0

## Purpose

Frozen, provenance-locked **real** multimodal gold input for T06 (and T09
consumer evaluation). This package is **not** a synthetic fixture and must not
be counted as Wave A contract samples.

## Modalities

| Modality | File | Role |
|----------|------|------|
| `table` | `raw/fishtrial_resistance.csv` | Primary machine-readable table (time vs resistance) |
| `chart` | `raw/Picture1.png` | Deposited multi-panel scientific plots (resistance / capacitance / real / imaginary impedance) |
| supporting tables | `raw/fishtrial_*.csv` | Underlying series for each panel |

All files come from the **same** Zenodo record and measurement.

## Source

- Title: Electrical impedance of food sensor recorded during fish spoilage
- Creators / provider: Beker, Levent (Koç University; ORCID 0000-0002-9777-6619; Zenodo `lbeker`)
- Landing: https://zenodo.org/records/13378442
- API: https://zenodo.org/api/records/13378442
- DOI / fixed version: `10.5281/zenodo.13378442`
- Publication date: 2024-08-27
- Source version basis: immutable Zenodo record 13378442 + DOI 10.5281/zenodo.13378442 + publication date 2024-08-27 (Zenodo `metadata.version` absent)
- Package version: `v1.0.0`
- Related paper: https://www.nature.com/articles/s43016-023-00750-9

## License

- Name: Creative Commons Attribution 4.0 International
- SPDX: `CC-BY-4.0`
- URI: https://creativecommons.org/licenses/by/4.0/legalcode
- Scope (Zenodo source): deposited CSV tables and `Picture1.png` in record 13378442
- Scope (team packaging): manifest, gold labels, validators, and docs are SAGE125 T06 team artifacts (not Zenodo deposit contents)
- Attribution: cite creators (Beker, Levent) and DOI `10.5281/zenodo.13378442` when using Zenodo source files
- Evidence: `license_evidence.md`, `raw/zenodo_landing_13378442.html`, `raw/zenodo_record_13378442.json`

## Assertions

- `is_synthetic: false`
- `is_provisional: false`
- `is_fixture: false`
- **This input is not synthetic, provisional, or a fixture.**
- Controlled artifact path: `NOT_APPLICABLE` (public Zenodo open deposit)

## Registry / handoff / reproduce surfaces

- Registry surface (T06 package; no shared repo-wide provenance registry file exists): `manifest.json`
- Reproduce surface: this file, section **Reproduce**
- Handoff surface: GitHub PR #29 description + external T09 handoff message
- Consistency matrix: `CONSISTENCY_MATRIX.md`

## Reproduce

From repository root (conda env `sage125` or project interpreter). Commands are
executable as written; they do not require substituting angle-bracket placeholders.

### Offline validate (no network)

```bash
python -B docs/modules/T06/gold/zenodo_fish_spoilage_impedance/v1.0.0/fetch_and_verify.py --validate
```

### Isolated fetch (creates a fresh empty temp directory automatically)

```bash
python -B -c "import subprocess,sys,tempfile; from pathlib import Path; w=Path(tempfile.mkdtemp(prefix='sage125-t06-fetch-')); raise SystemExit(subprocess.call([sys.executable,'-B','docs/modules/T06/gold/zenodo_fish_spoilage_impedance/v1.0.0/fetch_and_verify.py','--fetch','--workdir',str(w)]))"
```

Equivalent explicit PowerShell form (also creates a unique empty directory):

```powershell
$workdir = Join-Path $env:TEMP ("sage125-t06-fetch-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $workdir | Out-Null
python -B docs/modules/T06/gold/zenodo_fish_spoilage_impedance/v1.0.0/fetch_and_verify.py --fetch --workdir $workdir
```

`--fetch` re-downloads Zenodo science bytes into the empty workdir, verifies SHA-256
against `SHA256SUMS`, and **fails closed** on mismatch. It refuses repo paths,
non-empty directories, caches, fixtures, and synthetic fallbacks.

## Gold labels

- Path: `gold_labels.jsonl`
- Count: 100
- Table cells: exact match to deposited CSV
- Chart points: numeric gold from deposited CSVs (not model predictions), policy `t06-chart-error-v1`
- Note: table rows intentionally use JSON `null` for `bbox` / `series_id` / `coordinate_system` because those fields are chart-only (not placeholders)

## Domain mapping

See `domain_mapping.json` (`evaluation_case_id: T06-GOLD-FISH-IMPEDANCE-001`).
