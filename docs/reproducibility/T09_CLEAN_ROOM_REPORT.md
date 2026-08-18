# T09 Wave C Clean-room Report

`verified_at_wave_c=false`. `WAVE_C_DONE=false`. This report records isolated clean-room execution for Batch 4B; it is not a Wave C or release-candidate completion claim.

## Clean-room execution

`CLEAN_ROOM_EXECUTION=PASS`.

Accepted isolated execution head:

- `ACCEPTED_ACTUAL_EXECUTION_HEAD=d211a0c6dcadcecb28f3bbdbdea80c4681955f48`
- Evidence commit: `3889ac45486207c42db6fe7a9b2a1ae66206f3ef`
- Seven CI-equivalent gates and `--preflight-only` passed before the accepted execute.
- Formal `questions_125.json` SHA-256: `b6712a3b53f9776d7f695ea67f810c30b7d97ee59c183009432870d3224cdebb`
- No repository `.env` was present in the clean-room checkout.

T09-C-002 is PASS on this isolated clone/install/preflight/execute evidence. T09-C-001 packaging items remain blocked: there is still no approved 20-page technical-proposal PDF and no 125-file checksum inventory.

## Accepted 12-domain actual run

The accepted run is recorded in `T09_12_DOMAIN_ACTUAL_RUN_SUMMARY.json` and `T09_12_DOMAIN_ACTUAL_RUN_REPORT.md`.

- `BATCH_4B_ACTUAL_EXECUTION=COMPLETE`
- `METRIC_005_EXECUTION=PASS`
- `METRIC_005_VALIDATOR=PASS`
- `EVALUATED_DOMAIN_COUNT=12`
- `UNIQUE_DOMAIN_COUNT=12`
- `ACCEPTED_PROVIDER_CALLS=144`
- `ACCEPTED_REQUEST_ID_COUNT=144`
- `ACCEPTED_GLOBAL_ATTEMPT_COUNT=12`
- `MOCK_CALL_COUNT=0`
- `COST_USD=null`
- `COST_STATUS=unknown_or_provider_not_priced`
- `ACTUAL_ABLATION_AUTHORIZED=false`
- `ACTUAL_ABLATION_RUNS=0`

Deep Research usage omitted by the provider stays `input_tokens=null`, `output_tokens=null`, `total_tokens=null`. Those fields are not rewritten to `0`.

Superseded or failed Q001 attempts that are not in the accepted 144-call ledger are `unknown/not_consolidated`. They are not mixed into the accepted counts.

## Still blocked

- `T09_METRIC_003=BLOCKED`
- `T09_METRIC_004=BLOCKED`
- `RC_FINAL_STATUS=BLOCKED`
- `FINAL_TIP_ATTESTATION=PENDING`
- `PR_IS_DRAFT=true`

The packaging validator at `scripts/eval/validate_t09_packaging.py` remains fail-closed for missing 20-page/125-file inputs. It makes no network or Provider calls.
