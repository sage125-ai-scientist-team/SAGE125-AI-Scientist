# Render temporary preview runbook

## Scope and source

- Central repository: `sage125-ai-scientist-team/SAGE125-AI-Scientist`.
- Tracked branch: `integration/2026-08-10`.
- Render project/environment: `SAGE125-AI-Scientist-Preview` / `preview`.
- API service: `sage125-api-preview`.
- UI service: `sage125-ui-preview` (Streamlit Web Service).
- Region and plan: `singapore`, `free`.
- This is a temporary team preview, not a production environment.
- PR Preview Environments and custom domains remain disabled.

Previous deployment platform: Railway; its repository-only deployment configuration was removed, and no remote cloud resources were deleted.

## Build, start, and health checks

| Service | Build command | Start command | Health check |
| --- | --- | --- | --- |
| API | `pip install -r requirements.txt` | `python -m scripts.start_api` | `/health` |
| UI | `pip install -r requirements.txt` | `python -m scripts.start_ui` | `/_stcore/health` |

Both processes bind `0.0.0.0` and consume Render's `PORT`. The public entry points are expected to be:

- API: `https://sage125-api-preview.onrender.com`
- API docs: `https://sage125-api-preview.onrender.com/docs`
- UI: `https://sage125-ui-preview.onrender.com`

After the API service exists, set the UI-only non-secret variable `FRONTEND_API_BASE_URL` to the API's actual generated HTTPS URL. Do not hardcode that value in application source. The Blueprint also sets `FRONTEND_API_SHORT_TIMEOUT_SECONDS=10`, `FRONTEND_API_WAKE_TIMEOUT_SECONDS=75`, and `FRONTEND_INGEST_TIMEOUT_SECONDS=900`. The longer wake timeout lets a sleeping Free API start before the UI declares it unavailable; ingestion posts directly to `/ingest` and is never automatically retried because uploads are not idempotent.

## Automatic deployment

Both services use `autoDeployTrigger: checksPass`. A reviewed squash merge to `integration/2026-08-10` triggers the six real `quality-gates` jobs (`lint`, `type`, `unit`, `integration`, `security`, and `build`). Render deploys the new commit only after GitHub checks pass. Failed or absent checks must not be treated as success.

The final workflow is:

1. Team member opens a PR against `integration/2026-08-10`.
2. The captain reviews and manually squash-merges it.
3. GitHub runs push CI on the integration commit.
4. Render deploys the same commit after checks pass.
5. The fixed generated `onrender.com` addresses serve the new revision.

## Environment variables

The Blueprint contains only deterministic non-secret configuration. The two manual Model Studio variables are:

- `WORKSPACE_ID`
- `DASHSCOPE_API_KEY`

Add both only to `sage125-api-preview` in Render Dashboard > Environment after the credential-free deployment passes. Never add them to `sage125-ui-preview`, Git, this document, logs, issues, or chat. The values must belong to the same Alibaba Cloud Model Studio region and workspace.

The API starts without either value. `/health` reports Bailian as unavailable, and real model requests return service unavailable. The deployment does not switch to OpenRouter or Mock. Mock results are possible only when a user explicitly chooses Mock mode or CI explicitly sets `MOCK_LLM=true`.

## Temporary storage and data availability

`PREVIEW_EPHEMERAL_STORAGE=true`, `DATA_DIR=/tmp/sage125/data`, and `EXPORT_DIR=/tmp/sage125/exports` make the preview's storage mode explicit. Render Free Web Services do not provide a persistent disk. Uploaded files, the zvec index, jobs, feedback, SQLite state, and generated exports can disappear on restart, redeploy, spin-down, or instance replacement.

The integration branch intentionally does not track `data/processed`, `data/index`, PDFs, local databases, or exports. Consequently, the base preview can expose `/health`, `/docs`, `/openapi.json`, and the UI while reporting a missing question dataset until an approved redistributable source is added through a separate reviewed change. Do not claim this preview preserves task history or contains production data.

Free services can spin down after inactivity; the next request can incur a cold start of approximately one minute. The UI waits for that wake-up and reports an unconfirmed result separately from a definite rejection. Do not use an external keep-alive workaround.

## Verification and logs

For every deployment:

1. Confirm the active branch is `integration/2026-08-10` and the active commit equals the latest integration SHA.
2. Confirm the deploy is live and both health checks pass.
3. Request API `/health`, `/docs`, and `/openapi.json`, then UI `/` and `/_stcore/health`.
4. Confirm the UI calls the API's public HTTPS URL and does not request localhost.
5. Confirm missing Bailian credentials remain reported as unavailable and no Mock/OpenRouter fallback occurred.
6. Inspect build and runtime logs for error type and non-sensitive request IDs only. Never copy headers, environment values, database content, or derived Model Studio endpoints.

## Rollback

1. In the affected Render service's Deploys page, redeploy the last known-good successful integration deployment.
2. Verify the API and UI health endpoints and confirm both services run the same known-good commit.
3. Revert the faulty integration change through a reviewed GitHub PR; do not rewrite or force-push the integration branch.
4. Keep `checksPass` enabled. A production rollout requires a separate project/environment, persistent data design, explicit approval, and independent smoke tests.
