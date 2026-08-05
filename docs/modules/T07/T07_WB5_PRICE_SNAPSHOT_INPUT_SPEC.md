# T07-WB5 price snapshot input specification

Decision: **PRICE GATE — HOLD**

Schema version: `t07.price-snapshot-input.v1`

This contract defines the operator-supplied provenance and price input needed before the existing WB5 runtime `PriceSnapshot` may be constructed. It contains no actual model price, guessed price, live exchange rate, account value, or provider response. `PRICE_SNAPSHOT_REQUIRED` remains active.

## Required top-level fields

The input is a UTF-8 JSON object containing:

- `schema_version`: exactly `t07.price-snapshot-input.v1`
- `version`: non-empty operator snapshot version
- `obtained_at`: timezone-aware ISO-8601 timestamp
- `currency`: uppercase three-letter ISO 4217 code
- `pricing_unit`: exactly `per_1m_tokens`
- `source`: provenance object
- `models`: exact six-model object
- `fx`: required only when `currency != USD`
- `synthetic` and `test_only`: optional booleans; production inputs must omit them or set both false

Production CLI validation rejects any input with `synthetic=true` or `test_only=true`. Unit-test fixtures explicitly set both true and cannot be promoted to an actual snapshot.

## Source provenance

`source` requires `type`, `title`, `locator`, `captured_at`, and `content_sha256`.

Allowed source types are:

- `official_pricing_page`
- `official_account_page`
- `captain_material`

The title and locator must be non-empty and specific. Generic labels such as “官网” or “控制台” are insufficient. `captured_at` must be timezone-aware ISO-8601. `content_sha256` must be a 64-character lowercase SHA-256. Test provenance may not be presented as formal provenance.

Stable source errors include `PRICE_SOURCE_INVALID`, `PRICE_SOURCE_HASH_INVALID`, and `PRICE_TIMESTAMP_INVALID`.

## Exact model set

`models` must contain exactly these names, without aliases or extras:

1. `qwen3.6-flash`
2. `qwen3.7-plus`
3. `qwen3.7-max`
4. `qwen-deep-research`
5. `text-embedding-v4`
6. `qwen3-rerank`

A missing, extra, renamed, or automatically mapped model returns `PRICE_MODEL_SET_MISMATCH`.

## Decimal price fields and zero-price provenance

Every model requires `input_per_million`, `output_per_million`, and `conditions`.

Price values must be JSON strings matching `^(0|[1-9][0-9]*)(\.[0-9]+)?$`. Validation uses `Decimal` directly and never passes through `float`. Values must be finite and non-negative. Scientific notation, NaN, Infinity, negative values, `placeholder`, `TODO`, `unknown`, and `N/A` are rejected with `PRICE_DECIMAL_INVALID`.

Zero is not a representation for an unknown price. If an official source truly specifies zero, that model entry must also contain `zero_price_confirmed=true` and a specific `zero_price_source_locator`; otherwise validation returns `ZERO_PRICE_PROVENANCE_REQUIRED`.

## Conditions and price-tier selection

Every `conditions` object requires:

- `region=cn-beijing`
- `billing_basis=per_1m_input_output_tokens`
- a non-empty `tier`
- a non-empty `description`
- `applicability_confirmed=true`
- non-empty, unique `pricing_dimensions`
- `selected_dimensions`

Flat pricing must use only the `flat` dimension. Conditional pricing must name every relevant dimension and uniquely select its applicable value. Context-length, cache, batch, region, and tier distinctions cannot remain implicit. An incomplete or conflicting selection returns `PRICE_TIER_AMBIGUOUS`.

Per-call fees, per-task fees, non-token extra fees, or any unknown model-price component cannot be represented by the current `BudgetLedger`; they return `UNSUPPORTED_PRICE_COMPONENT`. The validator never silently drops a component.

## FX contract

For `currency=USD`, `fx` must be absent or null. For any other currency, `fx` requires:

- `from_currency` equal to the top-level currency
- `to_currency=USD`
- positive plain-string Decimal `usd_per_source_currency_unit`
- traceable `source`
- timezone-aware `obtained_at`
- `method=multiply_source_currency_price_by_usd_per_source_currency_unit`

The fixed formula is:

`USD = source_currency_price × usd_per_source_currency_unit`

Missing FX returns `FX_SNAPSHOT_REQUIRED`. Wrong direction, method, source, or rate returns `FX_CONVERSION_INVALID`. No live rate is fetched.

## Runtime normalization

Only a fully validated input may be converted in memory to the existing runtime mapping:

- `version`
- canonical, traceable `source` string
- timezone-aware `obtained_at`
- the exact six models with `input_per_million_usd` and `output_per_million_usd`

All conversion uses `Decimal`, and normalized Decimal values remain strings. The resulting mapping must pass `PriceSnapshot.from_mapping()`. Validation does not write back to the frozen WB5 config and does not replace its `price_snapshot=null` value.

## Offline CLI

Self-check:

`python -m scripts.batch_125.validate_price_snapshot --self-check`

Operator input:

`python -m scripts.batch_125.validate_price_snapshot --input <repository-external-json>`

Optional normalized output:

`python -m scripts.batch_125.validate_price_snapshot --input <repository-external-json> --normalized-output <repository-external-json>`

Input and normalized-output targets for production use must be outside the repository. Repository-internal normalized output returns `PRICE_SNAPSHOT_OUTPUT_PATH_INVALID`. Default output is a safe status summary: it never prints price values, account locators, API keys, Workspace IDs, `.env`, authorization headers, balances, or provider responses.

The validator uses only standard-library parsing, `Decimal`, datetime, hashing/regex rules, and the existing `PriceSnapshot`. It performs no network or provider call.

## Current status

- `actual_price_snapshot_supplied=false`
- `actual_price_snapshot_validated=false`
- `provider_calls=0`
- `provider_preflight_executed=false`
- `PRICE_SNAPSHOT_REQUIRED remains active`
- `FIVE_REAL_RUNS_BLOCKED remains active`
