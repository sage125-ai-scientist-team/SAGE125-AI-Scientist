# Known limitations

- The 12 calibration items are synthetic contract fixtures keyed by representative
  IDs, not the 12 source-booklet questions or actual five-artifact bundles.
- The T05 Q028 execution receipt is actual and checksum-bound, but it does not
  contain an authentic T03 AgentTrace; T03 correctly blocks the constructed audit.
- The T07 direct `GateResult` boundary is verified offline. The default T07 adapter
  still calls the legacy quality-gate entrypoint and needs a T07-owner change.
- No live five-question batch, production API, provider call, or T08 path was run.
- Metrics are in-process observations, not a production monitoring backend or SLO.
- Production SQLite backup/restore cutover was not run. Automated temporary-store
  restart, concurrency, idempotency, audit-chain and tamper detection are covered.
- The initial shared Python environment lacked Ruff/Coverage; installing the exact
  versions already locked by the repository made all 32 integration tests pass.
  Final remote GitHub checks still remain authoritative for the pushed HEAD.
