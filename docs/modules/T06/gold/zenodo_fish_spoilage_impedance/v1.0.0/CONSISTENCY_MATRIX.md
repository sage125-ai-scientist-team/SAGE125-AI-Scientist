# CONSISTENCY_MATRIX — zenodo_fish_spoilage_impedance v1.0.0

Surfaces:

| Surface | Path / location |
|---------|-----------------|
| Registry | `manifest.json` (T06 package registry surface; repository has no shared canonical provenance registry file) |
| Manifest | `manifest.json` |
| Handoff | GitHub PR #29 description + external T09 handoff message |
| REPRODUCE | `README.md` section **Reproduce** |
| Source metadata | `source_metadata.json` |
| Checksums | `SHA256SUMS` |

| Field | Registry/Manifest | Handoff | REPRODUCE | Source metadata | Result |
|-------|-------------------|---------|-----------|-----------------|--------|
| package/dataset ID | zenodo_fish_spoilage_impedance | same | same | title/DOI linked | PASS |
| title | source_title | same | Source section | title | PASS |
| source landing URI | https://zenodo.org/records/13378442 | same | same | source_landing_uri | PASS |
| source API URI | source_api_uri | same | same | source_download_api | PASS |
| Zenodo record | 13378442 | same | same | zenodo_record_id | PASS |
| DOI | 10.5281/zenodo.13378442 | same | same | doi | PASS |
| source version basis | source_version_basis | same | same | source_version_basis | PASS |
| package version | v1.0.0 | same | same | package_version | PASS |
| publication date | 2024-08-27 | same | same | publication_date | PASS |
| creators/provider | creators + provider_depositor | same | same | creators + provider_depositor | PASS |
| license | CC-BY-4.0 | same | same | license.spdx | PASS |
| license scope | zenodo source vs team packaging split | same | same | license_scope | PASS |
| gold label count | 100 | same | same | n/a (labels file) | PASS |
| domain mapping | domain_mapping.json | same | Domain mapping section | n/a | PASS |
| chart policy | t06-chart-error-v1 | same | Gold labels section | n/a | PASS |
| synthetic/provisional/fixture | all false | same | Assertions | n/a | PASS |
| validate command | reproducible_validate_command | same | Reproduce | n/a | PASS |
| fetch command | reproducible_fetch_command (mkdtemp one-liner) | same | Reproduce | n/a | PASS |
| package path | docs/modules/T06/gold/zenodo_fish_spoilage_impedance/v1.0.0 | same | implied | n/a | PASS |
| controlled artifact | NOT_APPLICABLE + na_reason | same | Assertions | n/a | PASS |
| SHA-256 inventory | files{} + SHA256SUMS | full inventory in handoff | points to SHA256SUMS | content URIs | PASS |

Explained non-placeholder nulls:

- `gold_labels.jsonl` table rows: `bbox`, `series_id`, `coordinate_system` are JSON null because they are chart-only fields (N/A for table modality).
