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

- Landing: https://zenodo.org/records/13378442
- DOI / fixed version: `10.5281/zenodo.13378442`
- Publication date: 2024-08-27
- Title: Electrical impedance of food sensor recorded during fish spoilage
- Related paper: https://www.nature.com/articles/s43016-023-00750-9

## License

- Name: Creative Commons Attribution 4.0 International
- SPDX: `CC-BY-4.0`
- URI: https://creativecommons.org/licenses/by/4.0/legalcode
- Scope: entire Zenodo record 13378442 (CSV + PNG)
- Evidence: `license_evidence.md`, `raw/zenodo_landing_13378442.html`, `raw/zenodo_record_13378442.json`

## Assertions

- `is_synthetic: false`
- `is_provisional: false`
- `is_fixture: false`
- **This input is not synthetic, provisional, or a fixture.**

## Reproduce

From repository root (conda env `sage125` or project interpreter):

```bash
python docs/modules/T06/gold/zenodo_fish_spoilage_impedance/v1.0.0/fetch_and_verify.py --validate
python docs/modules/T06/gold/zenodo_fish_spoilage_impedance/v1.0.0/fetch_and_verify.py --fetch
```

`--fetch` re-downloads Zenodo bytes and **fails** if SHA-256 differs from `SHA256SUMS`.

## Gold labels

- Path: `gold_labels.jsonl`
- Table cells: exact match to deposited CSV
- Chart points: numeric gold from deposited CSVs (not model predictions, not invented digitization), relative tolerance 5% per T06 chart DoD

## Domain mapping

See `domain_mapping.json` (`evaluation_case_id: T06-GOLD-FISH-IMPEDANCE-001`).
