# Railway staging deployment runbook

## Scope and topology

- Railway project: `SAGE125-AI-Scientist`.
- Persistent environment `staging` follows `integration/2026-08-10`.
- Persistent environment `production` follows `main`, but autodeploy remains disabled and no production deployment is performed in this rollout.
- `sage125-api` and `sage125-ui` use the central source repository `sage125-ai-scientist-team/SAGE125-AI-Scientist`.
- PR environments stay disabled because team review and staging promotion happen through the shared integration branch.
- Staging and production must never share a database or volume.

## Service configuration

| Service | Config file | Build | Start | Healthcheck | Replicas |
| --- | --- | --- | --- | --- | --- |
| `sage125-api` | `/railway-api.toml` | Railpack Python detection from `requirements.txt` | `python scripts/start_railway_api.py` | `/health` | 1 |
| `sage125-ui` | `/railway-ui.toml` | Railpack Python detection from `requirements.txt` | `python scripts/start_railway_ui.py` | `/_stcore/health` | 1 |

Both entrypoints bind `0.0.0.0` and read Railway's `PORT`. Generate one fixed public Railway domain per service. The UI must use the API service through `FRONTEND_API_BASE_URL`; it must not call Model Studio or hold Model Studio credentials.

## Staging variables

Configure these non-secret values on `staging` / `sage125-api`:

- `APP_ENV=staging`
- `LOG_LEVEL=INFO`
- `LLM_PROVIDER=bailian`
- `DASHSCOPE_REGION=cn-beijing`
- `QWEN_FAST_MODEL=qwen3.6-flash`
- `QWEN_BALANCED_MODEL=qwen3.7-plus`
- `QWEN_STRONG_MODEL=qwen3.7-max`
- `QWEN_DEEP_RESEARCH_MODEL=qwen-deep-research`
- `EMBEDDING_BACKEND=bailian`
- `BAILIAN_EMBEDDING_MODEL=text-embedding-v4`
- `BAILIAN_RERANK_MODEL=qwen3-rerank`
- `MOCK_LLM=false`
- `DATA_DIR=/data`
- `EXPORT_DIR=/data/exports`
- `CORS_ALLOW_ORIGINS` set to the fixed HTTPS `sage125-ui` origin only.

Configure these non-secret values on `staging` / `sage125-ui`:

- `APP_ENV=staging`
- `LOG_LEVEL=INFO`
- `FRONTEND_RUN_VIA_API=1`
- `FRONTEND_API_BASE_URL` set to the `sage125-api` Railway private-network reference.

The only manual Model Studio values are `WORKSPACE_ID` and `DASHSCOPE_API_KEY`. Add them only to `staging` / `sage125-api`, through Railway Variables. They must belong to the same Alibaba Cloud Model Studio region and workspace. Never add them to the UI, Git, a PR, a log, a client-prefixed variable, or this document. The server derives compatible-mode and Deep Research base URLs from `DASHSCOPE_REGION` and `WORKSPACE_ID`.

Optional external integrations (`OPENALEX_API_KEY`, `CONTACT_EMAIL`, and `OUTBOUND_HTTPS_PROXY`) are not required for the base staging deployment. Missing optional integrations must remain clearly reported as optional/unavailable.

## Persistent storage

Attach a staging-only Railway volume to `sage125-api` at `/data`. `DATA_DIR=/data` stores uploaded sources and the zvec index; `EXPORT_DIR=/data/exports` stores reports and the SQLite job database. Keep the API at one replica because SQLite and the local vector store are single-writer resources. The UI has no volume. A future production rollout must create a different production-only volume and must not copy staging data implicitly.

After the first active deployment, validate persistence by creating a non-sensitive test record or upload, recording only its identifier, redeploying the same commit, and confirming the identifier remains. Do not print database contents or connection secrets.

## GitHub autodeploy and CI

For both staging services:

1. Connect the central repository and select `integration/2026-08-10`.
2. Enable autodeploy.
3. Enable **Wait for CI**.
4. Keep PR environments disabled.

The `quality-gates` workflow runs on pushes and pull requests targeting both `integration/2026-08-10` and `main`. With Wait for CI enabled, a new integration commit must move Railway through `WAITING`, then build/deploy only after all GitHub checks pass. A failed check must result in a skipped deployment.

For production, select `main` but keep autodeploy disabled. Do not deploy production during the staging rollout.

## Credential-free behavior and smoke checks

Before the two manual Model Studio values exist, both processes must start. `GET /health` returns HTTP 200 for the process while exposing only a boolean Model Studio configuration state; it must not expose a key, workspace identifier, or derived base URL. Real model requests return a clear service-unavailable response and never fall back to Mock or another provider.

Base staging checks:

- API: `/health`, `/docs`, `/openapi.json`, `/questions`, and safe read-only endpoints.
- UI: `/` and `/_stcore/health`; browser traffic must not target localhost or contain Model Studio credentials.
- Storage: `/data` is the mounted staging volume and the API has one replica.
- Deployment: active branch and commit match the latest successful integration push.

After the two manual values are applied, run one minimal real Qwen smoke request with a short fixed response and a very small token limit. Verify provider `bailian`, the frozen model name, an upstream request ID when available, and no Mock/OpenRouter fallback. Never copy the response headers, key, workspace ID, or full derived endpoint into an issue or log.

## Logs and incident checks

Inspect build, deploy, healthcheck, and application logs for exception type and request ID only. Do not print environment values, authorization headers, the workspace ID, the derived base URL, database content, or Railway/GitHub credentials. A repeated restart, failed `/health`, or failed volume initialization is a deployment failure and must not be hidden by a weakened healthcheck.

## Rollback

1. Disable staging autodeploy temporarily if repeated integration pushes would compound the incident.
2. In the affected service deployment history, redeploy the last known-good successful integration deployment. Keep the fixed public domain and the same staging volume attached.
3. Verify `/health`, `/docs`, the UI health endpoint, active commit, and storage persistence.
4. Revert the faulty integration change through a reviewed GitHub PR; do not force-push or rewrite `integration/2026-08-10`.
5. Re-enable autodeploy and Wait for CI after the corrective checks pass.

Production rollback uses the same reviewed-commit principle but a separate production volume. Production activation requires a separate approval, an isolated database/volume, explicit smoke tests, and continued disabled autodeploy until the release decision is made.
