# T08 Ten-Minute Demo Runbook

状态：`SYNTHETIC_REHEARSAL_READY / PRODUCTION_WAIT`

## 0:00–0:45 — Truth and environment

1. Show the active commit and environment.
2. State whether the run is production or synthetic.
3. For the current rehearsal say exactly:

```text
This is a fixture-explicit planned rehearsal. It is not actual execution and
does not prove production owner integration.
```

## 0:45–1:45 — Start one job

1. Select Q001.
2. Select the explicit mode.
3. Click Run once.
4. Show `job_id`, `correlation_id`, status, stage, attempt, and timeout.
5. Refresh once to demonstrate server-side recovery.

## 1:45–3:00 — Evidence

Show the same job's:

- quoted text;
- source and locator;
- author/year;
- support/contradict relation;
- confidence and verification status.

Do not describe the fixture evidence as newly retrieved production literature.

## 3:00–4:15 — Reviewer, versions, and diff

1. Show V1 Reviewer issue and scores.
2. Show V2 lineage and resolved issue.
3. Show the owner-provided V1→V2 structured diff.
4. State that T08 displays the diff and does not recompute issue closure.

## 4:15–5:30 — Feedback

1. Submit one idempotent feedback request.
2. Show the returned feedback ID and canonical target version.
3. Query decision status.
4. In the current package, deliberately show
   `UPSTREAM_CONTRACT_UNAVAILABLE`.
5. State that no resulting version is fabricated while T03/T02 read ports are missing.

## 5:30–6:45 — Gate and execution truth

1. Show Validation Gate projection.
2. Show `NOT ACTUAL`.
3. Show execution status `planned`.
4. Read the warning that the experiment has not actually run.

Never say that file existence or a chart proves actual execution.

## 6:45–7:45 — Multimodal

Show:

- source;
- page and bbox;
- units;
- confidence;
- validation status;
- human-review warning.

Low-confidence data must remain visible.

## 7:45–9:00 — Three-format export

1. Request JSON, Markdown, and PDF for the same job.
2. Show three artifact records, sizes, hashes, and truth status.
3. Download each through the controlled API.
4. Open the PDF and show planned / NOT ACTUAL / limitation text.

## 9:00–9:40 — Recovery and isolation

1. Refresh the browser and recover from URL `job_id`.
2. Show that the same job is restored.
3. Cite the five-job and cross-actor evidence.

## 9:40–10:00 — Honest close

End with:

```text
Synthetic browser rehearsal: PASS.
Production E2E, Docker clean deployment, 120-minute stability, T07 review, and
T09 acceptance: WAIT.
```

## Failure fallback

- API unavailable: show correlation ID and fail-closed message; do not use old cache.
- Owner port unavailable: show WAIT; do not switch to fixture without re-labeling.
- PDF generation fails: use JSON/Markdown only and mark PDF gate FAIL.
- Network unavailable: use the backup recording only if it corresponds to the same final SHA.
