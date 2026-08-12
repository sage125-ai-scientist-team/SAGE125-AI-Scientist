# Byte semantics for zenodo_fish_spoilage_impedance v1.0.0

## Zenodo source bytes (`source_bytes`)

Files under `raw/` that are Zenodo download payloads:

- `raw/fishtrial_*.csv`
- `raw/Picture1.png`

These MUST equal the HTTP response body bytes from the fixed Zenodo record
`10.5281/zenodo.13378442` file endpoints, before any decode/newline rewrite.

Equivalence required:

`Zenodo source bytes == Git blob bytes == fresh-clone worktree bytes == SHA256SUMS`

## Evidence snapshots

- `raw/zenodo_record_13378442.json`: frozen Zenodo API record JSON response body
  (opaque `-text` bytes once frozen).
- `raw/zenodo_landing_13378442.html` / `raw/cc_by_4_0_legalcode.html`: frozen
  HTML evidence snapshots (opaque `-text` bytes once frozen).

## Deterministic derived text

- `manifest.json`
- `domain_mapping.json`
- `source_metadata.json`
- `gold_labels.jsonl`
- `SHA256SUMS` (inventory of others; never lists itself)
- docs / `fetch_and_verify.py`

Rules:

- UTF-8, no BOM
- LF only
- exactly one trailing LF
- stable JSON key order / JSONL row order
- POSIX relative paths
- no absolute paths, temp dirs, wall-clock timestamps, or durations inside
  hashed derived scientific artifacts

`manifest.json` MUST NOT embed its own SHA-256 or the `SHA256SUMS` SHA-256.

## Worktree

Worktree is not an independent normative object. After a fresh clone with the
package-local `.gitattributes`, worktree bytes MUST equal Git blob bytes and
MUST NOT depend on a developer's `core.autocrlf`.

## Chart error policy v1

```
gold != 0:
  relative_error = abs(predicted - gold) / abs(gold)
  pass <=> relative_error <= 0.05

gold == 0:
  absolute_error = abs(predicted - gold)
  pass <=> absolute_error <= declared_absolute_tolerance
```

- `EPS_USED=NO` (no `max(abs(gold), eps)`).
- Near-zero non-zero values still use relative error.
- Declared zero absolute tolerance for this package chart points:
  - value: `0.0`
  - unit: series unit (`ohm` or `F`)
  - basis: deposited CSV provides exact numeric gold; a CSV value of exactly
    `0` means exact zero in the source deposit (instrument export), so absolute
    tolerance is `0.0` in that unit.
