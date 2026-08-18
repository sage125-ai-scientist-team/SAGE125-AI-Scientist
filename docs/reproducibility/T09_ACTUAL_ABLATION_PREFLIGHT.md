# T09 Actual Ablation Preflight

`ACTUAL_ABLATION_AUTHORIZED=false` · `PROVIDER_CALL_BUDGET=0` · `DRY_RUN_ONLY=true` · `FAIL_CLOSED=true`.

Planned configuration IDs are `full-system`, `no-RAG`, `no-reviewer`, `no-HITL`, and `single-agent`. Each must record its immutable configuration projection and disable only its named component; validation must compare the projected configuration against full-system to reject no-op “ablations”.

Before authorization, every run is blocked on a fixed input manifest/hash, this registry/hash, provider/model/version/endpoint identity, retrieval-index input/checksum, question range, seed, repetitions, per-config and total call caps, raw and sanitized output locations, token/call/cost fields, retry/resume policy, stop conditions, reproduction command and metric denominators. These values are currently `PENDING_SEPARATE_ACTUAL_ABLATION_AUTHORIZATION`; no historical default is an approval.

All output states must be one of `planned`, `dry-run`, `mock`, `offline`, or `actual`; no dry-run or mock output may be represented as actual.
