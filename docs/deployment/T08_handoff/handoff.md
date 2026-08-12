# T08 Wave C Handoff

状态：`RELEASE_CANDIDATE_PACKAGE / PRODUCTION_E2E_WAIT`

## Purpose

T08 provides the authenticated asynchronous API, API-only Streamlit console,
secure artifacts/exports, T03 feedback submission, T06 detail projection,
container configuration, and release evidence.

## Entry points

```text
API:      python -m scripts.start_api
Streamlit: streamlit run frontend/streamlit_app.py
Compose:  docker compose up -d --wait
```

## Key classes and functions

- `app.api.main.create_app`: composition root;
- `app.api.job_store.SQLiteJobStore`: durable job/event state;
- `app.api.artifact_registry.SQLiteArtifactRegistry`: ownership and checksum boundary;
- `app.api.owner_composition.T03FeedbackSubmitAdapter`: submit-only T03 adapter;
- `app.api.owner_composition.T06MultimodalReadAdapter`: frozen T06 detail adapter;
- `app.export.service.ExportService`: canonical JSON/Markdown/PDF export.

## Configuration

- API auth: `SAGE_API_KEYS_JSON`;
- UI API connection: `SAGE_UI_API_BASE_URL`, `SAGE_UI_API_KEY`;
- persistent roots: `DATA_DIR`, `EXPORT_DIR`, `T06_MULTIMODAL_STORE_DIR`;
- model credentials are runtime-only and never copied into the image.

See:

- `../T08_WAVE_C_CONTAINER_RUNBOOK.md`
- `../T08_WAVE_C_OWNER_COMPOSITION.md`

## Verification

Current verified development evidence:

```text
tests/api: 85 passed, 5 existing warnings
host short probe attempt 2: 91.258 seconds, failure_count=0
browser synthetic rehearsal: PASS
PDF synthetic page QA: PASS
production browser E2E: WAIT
Docker runtime verification: WAIT_NO_DOCKER
120-minute stability: WAIT_NO_DOCKER
```

## Release evidence index

- `acceptance_evidence/browser_rehearsal.md`
- `acceptance_evidence/pdf_qa/`
- `acceptance_evidence/api_examples.md`
- `acceptance_evidence/openapi_snapshot.json`
- `acceptance_evidence/export_consistency_report.md`
- `acceptance_evidence/clean_deployment_report.md`
- `acceptance_evidence/review_acceptance.md`
- `acceptance_evidence/known_limitations.md`
- `demo_runbook.md`
- `backup_recording.md`
- `rollback.md`
- `pr_links.txt`

## Truth boundary

The browser and PDF artifacts in this package use committed API fixtures and a
planned synthetic runner. They verify UI behavior, fail-closed semantics, and
export formatting only. They do not prove production owner composition,
actual execution, or a resulting feedback revision.

## Open blockers

- T01 Evidence read port: Issue #52;
- T02 version/diff read ports: Issue #53;
- T05 execution read port: Issue #54;
- T03 decision/resulting-version/Gate read port is not frozen;
- Docker and 120-minute environments are unavailable;
- T07 paired review and T09 deployment acceptance are unsigned.

## Final acceptance rule

This package must remain `WAIT` until a clean final SHA is used for production
browser E2E, Docker clean deployment, 7200-second stability, T07 sign-off, and
T09 sign-off. No fixture screenshot or planned PDF may replace those gates.
