# T07-WB5 v2 token-only budget policy

Approval date: 2026-08-07 (Asia/Shanghai)

Captain approval reference: `captain-option-b-approved-2026-08-07`

This document records the captain-approved Option B amendment. It removes the
price-snapshot, USD cost-limit, and completed cost-accounting requirements only
for the versioned WB5 v2 freeze. It does not authorize provider preflight or a
five-question run.

## Version identity

- Freeze ID: `T07-WB5-20260807-v2`
- Batch schema: `t07.batch.v2`
- Checkpoint schema: `t07.checkpoint.v2`
- Budget policy: `t07.budget.token-only.v2`
- Budget mode: `token_only`
- Cost accounting required: false
- Price snapshot required: false

The approved freeze ID, all three versions, and captain reference must match.
A bare `token_only` string cannot bypass the policy gate.

## Frozen inputs retained unchanged

The five IDs remain `Q001`, `Q028`, `Q050`, `Q075`, and `Q107`. Their complete
question text, domains, canonical input hashes, provider, route, six models,
model version, Prompt version/hash, production source, and T01/T03 interfaces
are byte-for-byte the values from v1. Only the versioned budget policy and
batch/checkpoint schema identity change.

## Token limits

| Scope | Limit |
|---|---:|
| Per question | 200,000 tokens |
| Five-question batch | 1,000,000 tokens |
| Maximum output per call | 8,192 tokens |

Every call, including retries, accumulates into the question and batch token
totals. Re-reading the same sanitized request ID is idempotent and does not
double count. Question, batch, or per-call token exhaustion returns
`BUDGET_EXHAUSTED`.

## Null-cost semantics

Under `token_only`, `cost_limit_usd`, `cost_used_usd`,
`estimated_cost_usd`, `settled_cost_usd`, and `price_snapshot_version` are
`null` or absent according to their versioned contract. Unknown cost is never
represented by numeric zero and `not_evaluated` is never accepted in a Decimal
field. No USD value is accumulated or compared.

The legacy `token_and_cost` mode retains `PRICE_SNAPSHOT_REQUIRED`,
`UNKNOWN_COST`, non-negative Decimal accounting, and USD limit enforcement.
The price input specification, JSON Schema, validator, tests, and evidence are
retained for those cost-enabled runs.

## Actual-call audit

`llm_call_audit.json` remains mandatory for completion. The v2 record carries
`cost_accounting_mode=token_only` while preserving provider, model, route tier,
timezone-aware timestamp, sanitized request ID, Prompt identity, input/output/
total tokens, retry attempt, and fallback. `fallback=true`, missing token usage,
provider/model drift, raw request IDs, or non-null cost fields fail closed.

## Checkpoint and resume

A `t07.checkpoint.v2` record binds batch schema, budget policy version and mode,
captain waiver, freeze ID, provider/model/route, model and Prompt versions,
Prompt hash, source hash, input hash, question identity, attempt, and embedded
v2 job. A v1 checkpoint cannot resume a v2 job and returns
`CHECKPOINT_SCHEMA_MISMATCH`; policy drift returns
`BUDGET_POLICY_MISMATCH`. No executed v1 state is automatically migrated.

## Preflight and completion

The v2 offline preflight still verifies the production sources, five mappings,
Prompt and schema files, provider configuration boolean, T01 ancestry/public
interface, T03 public interfaces, approved policy identity, and clean worktree.
It does not require a price snapshot and never calls a provider by default.

Completion still requires T01/T03, no open P0/P1, the five required artifacts,
registered and truthful call audit, manifest integrity, delivery-index
integrity, explicit token evidence, and verified policy identity. Missing cost
does not block v2; missing audit or token truth still blocks it.

## Reporting rule

Delivery records expose `budget_policy_version`, `budget_mode`,
`cost_accounting_required=false`, `price_snapshot_required=false`, and the
captain reference. Cost fields are null. Reports must state: costs were not
collected under the captain-approved token-only policy. They must not claim
that cost accounting was completed or invent a cost estimate.
