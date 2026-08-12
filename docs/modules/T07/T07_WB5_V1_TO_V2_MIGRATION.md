# T07-WB5 v1 to v2 migration rule

The migration is intentionally non-automatic.

1. Keep `T07-WB5-20260803-v1`, `t07.batch.v1`,
   `t07.checkpoint.v1`, all price-snapshot material, and historical evidence
   read-only as records of the original `token_and_cost` policy.
2. Create a new batch from `T07-WB5-20260807-v2` using `t07.batch.v2`,
   `t07.checkpoint.v2`, and `t07.budget.token-only.v2`.
3. Do not resume any v1 checkpoint into v2. The stable result is
   `CHECKPOINT_SCHEMA_MISMATCH`; no provider call, retry state, token count, or
   completed artifact is copied.
4. Within v2, reject freeze or budget-policy drift before restoring state.
5. Preserve the five frozen questions, canonical hashes, provider/model/route,
   Prompt identity, source identity, and quality gates unchanged.

This amendment changes execution eligibility, not history. It waives WB5 price
and cost-completion gates while retaining token limits and call-audit truth. It
does not authorize provider preflight, five real runs, Ready transition, or
merge.
