# T08 Rollback

## Trigger

Rollback when any of these occurs:

- health dependency becomes unavailable;
- job/artifact identity crosses actor or question;
- Mock/planned data is shown as actual;
- feedback or export idempotency breaks;
- container restart loses declared persistent state;
- PDF truth labels or references are wrong.

## Docker rollback

1. Record the failing image digest and commit.
2. Stop new writes.
3. Redeploy the last reviewed image tag without deleting named volumes.
4. Verify API and UI health.
5. Query existing job and artifact records.
6. Re-enable traffic only after ownership and truth checks pass.

```powershell
docker compose down
$env:SAGE125_IMAGE_TAG = "<last-reviewed-tag>"
docker compose up -d --wait
```

The current compose file does not yet consume `SAGE125_IMAGE_TAG`; final release
automation must either pin the image digest or document the exact reviewed tag.

## Git rollback

Create a reviewed revert PR against `integration/2026-08-10`. Do not force-push,
rewrite integration history, or push directly to integration/main.

## Data rollback

- Keep `sage125-data`, `sage125-exports`, and `sage125-multimodal`.
- Do not use `docker compose down --volumes` during rollback.
- SQLite migrations must remain backward-compatible or provide an owner-approved migration.

## Verification

After rollback:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8501/_stcore/health
docker compose ps
```

Then verify one pre-existing job, artifact checksum, and export download using its original actor.
