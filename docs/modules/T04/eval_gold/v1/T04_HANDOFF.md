# T04 Wave B Actual Gold Candidate Handoff

## Status

This package is an actual gold candidate submission for T09 provenance validation.

It is **NOT_CLAIMED_IN_FORMAL_CORPUS**. Final corpus inclusion remains subject to
T09 validation and captain approval.

## Task

- task_id: T04
- wave: B
- artifact_role: question_source

## Artifact

- artifact_name: `sjtu-booklet.pdf`
- artifact_type: `booklet`
- local_candidate_path: `data/raw/sjtu-booklet.pdf`
- size_bytes: `8422081`
- sha256: `4bda50e8e3c90f8968f1bfd72ded4d9587ae80cd40ba66656a12c93abcf8e576`

## Archive Chain

- archive_name: `sjtu-booklet.zip`
- controlled_archive_path: `data/raw/sjtu-booklet.zip`
- archive_size_bytes: `7405356`
- archive_sha256: `f2cc232d0f40ec125593dbecede98dc55093e7ec4c9e29f2bef10e64c1a185`
- extracted_member: `sjtu-booklet.pdf`
- extraction_method: PowerShell `Expand-Archive` into an isolated directory

The PDF comes from an original archive already held locally by a project member
and retained under internal project control.

## Provenance and Custody

- artifact identity: verified against the SHA-256 recorded in the historical
  PR #23 captain review
- source_type: `INTERNAL_CONTROLLED_ARTIFACT`
- provider: `INTERNAL_CONTROLLED_ARTIFACT`
- custodian: `INTERNAL_CONTROLLED_ARTIFACT`
- version: `PENDING_CONFIRMATION`
- public source URI: not claimed and not generated
- public license: not claimed
- internal authorization scope: `INTERNAL_PROJECT_TEAM_USE`
- authorization statement: authorized for controlled use within the project
  team; no public-source or redistribution claim is made
- T09 acceptance: `PENDING_CONFIRMATION`

The archive and extracted PDF byte identities are recorded as a controlled
internal provenance chain. Formal-corpus acceptance remains pending T09
validation and captain approval.

## Validation Boundary

This candidate must satisfy:

- reproducible controlled archive acquisition and extraction
- stable SHA-256 identity
- documented internal custody and authorization scope
- non-synthetic, non-provisional, non-fixture declaration

## Corpus Status

`NOT_CLAIMED_IN_FORMAL_CORPUS`
