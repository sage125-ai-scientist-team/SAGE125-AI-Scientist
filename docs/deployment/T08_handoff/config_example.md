# Runtime Configuration Example

PowerShell session-only configuration:

```powershell
$env:SAGE125_DEMO_API_KEY = "replace-with-local-key-at-least-12-characters"
$env:SAGE125_ISOLATION_API_KEY = "replace-with-second-local-key"
$env:DASHSCOPE_API_KEY = "<optional-runtime-secret>"
$env:WORKSPACE_ID = "<optional-runtime-workspace>"
docker compose up -d --wait
```

Rules:

- never commit a real `.env`;
- `.dockerignore` excludes `.env` from build context;
- Dockerfile uses allowlisted COPY only;
- API/UI keys are passed at runtime;
- the two local actor keys must differ;
- omit model credentials for an explicitly Mock/planned demo;
- missing model credentials must not trigger an unlabelled provider fallback.

No schema migration is required for the new T03 feedback SQLite store; it uses
its owner-managed initialization. Final multi-instance deployment still
requires T09 review of SQLite volume and writer topology.
