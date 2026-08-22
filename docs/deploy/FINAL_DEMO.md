# SAGE125 final frozen demo

Local Phase A only until captain authorization.

- API start: `PORT=8091 python -m scripts.start_final_api`
- UI start: `PORT=8591 ALLOW_LOCALHOST_API=1 API_BASE_URL=http://127.0.0.1:8091 python -m scripts.start_final_ui`
- Health: API `/health`, UI `/health`
- OpenAPI: `/docs`, `/openapi.json`
- RC: `deployment/frozen_rc/manifest.json`

Public Render demo will set `ALLOW_PUBLIC_ACTUAL_RUN=false` and will not receive Bailian secrets.

`starter` is used instead of `free` so the two-hour stability window is not killed by free-tier spin-down.
