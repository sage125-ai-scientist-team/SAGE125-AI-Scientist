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

Native Render `checksPass` / `commit` auto-deploy is **off**. The central repo is public, the GitHub org has no Render GitHub App, and the repo has no webhooks, so Render never receives push or check events. Treat a missing or failed GitHub check as not passed; do not ask Render to guess.

A reviewed squash merge to `integration/2026-08-10` runs `quality-gates` (`lint`, `type`, `unit`, `integration`, `coverage`, `security`, and `build`). Only after every required job succeeds, the `preview-deploy` job calls the Render API for `sage125-api-preview` and `sage125-ui-preview` with that integration SHA. Failed CI must not trigger a deploy.

Required GitHub Actions repository secret:

- `RENDER_API_KEY`: a Dashboard API key (`rnd_...`) from Account Settings. Never commit it. CLI session tokens expire and must not be used as the long-lived secret.

The final workflow is:

1. Team member opens a PR against `integration/2026-08-10`.
2. The captain reviews and manually squash-merges it.
3. GitHub runs push CI on the integration commit.
4. After those checks succeed, `preview-deploy` triggers both Render preview services for the same SHA.
5. The fixed generated `onrender.com` addresses serve the new revision.

## Environment variables

The Blueprint contains only deterministic non-secret configuration. The two manual Model Studio variables are:

- `WORKSPACE_ID`
- `DASHSCOPE_API_KEY`

Add both only to `sage125-api-preview` in Render Dashboard > Environment after the credential-free deployment passes. Never add them to `sage125-ui-preview`, Git, this document, logs, issues, or chat. The values must belong to the same Alibaba Cloud Model Studio region and workspace.

The API starts without either value. `/health` reports Bailian as unavailable, and real model requests return service unavailable. The deployment does not switch to OpenRouter or Mock. Mock results are possible only when a user explicitly chooses Mock mode or CI explicitly sets `MOCK_LLM=true`.

## Temporary storage and data availability

`PREVIEW_EPHEMERAL_STORAGE=true`, `DATA_DIR=/tmp/sage125/data`, and `EXPORT_DIR=/tmp/sage125/exports` make the preview's storage mode explicit. Render Free Web Services do not provide a persistent disk. Uploaded files, the zvec index, jobs, feedback, SQLite state, and generated exports can disappear on restart, redeploy, spin-down, or instance replacement.

The integration branch intentionally does not track `data/processed`, `data/index`, PDFs, local databases, or exports. Do not claim this preview preserves task history or contains production data.

Question catalog bootstrap (API start):

1. Prefer the packaged official mapping `data/catalog/official_questions_125.json` (titles and domains only; no booklet excerpts). `GET /questions` and `GET /health/catalog` read `OfficialQuestionCatalog`.
2. A real booklet extract at `data/processed/questions_125.json` remains the T07/T09 SHA-pinned source with excerpts; it is gitignored and is not required on Render.
3. Preview Seed is allowed only when `APP_ENV=development` and `SAGE125_ALLOW_PREVIEW_SEED=true`. `APP_ENV=preview`, `PREVIEW_EPHEMERAL_STORAGE`, and `SAGE125_PREVIEW_SEED` must not write or display placeholder titles.
4. The UI must keep calling the API (`FRONTEND_RUN_VIA_API=1` / T08 `frontend/**`); it does not invent questions client-side.
5. `/health.questions_count` and `GET /questions` read the same runtime path. `questions_count=0` after a preview start is a real failure, not a silent empty UI.

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
4. Keep native Render auto-deploy off until a Render GitHub App is installed and verified. Preview deploys stay gated by `quality-gates`. A production rollout requires a separate project/environment, persistent data design, explicit approval, and independent smoke tests.
