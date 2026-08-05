"""Offline validation and normalization for operator-supplied price inputs."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Final

from app.batch.actual_call_audit import PriceSnapshot
from app.batch.errors import BatchRunnerError


PRICE_SNAPSHOT_INPUT_SCHEMA_VERSION: Final[str] = (
    "t07.price-snapshot-input.v1"
)
FROZEN_PRICE_MODELS: Final[tuple[str, ...]] = (
    "qwen3.6-flash",
    "qwen3.7-plus",
    "qwen3.7-max",
    "qwen-deep-research",
    "text-embedding-v4",
    "qwen3-rerank",
)
ALLOWED_SOURCE_TYPES: Final[frozenset[str]] = frozenset(
    {
        "official_pricing_page",
        "official_account_page",
        "captain_material",
    }
)
DECIMAL_STRING_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^(0|[1-9][0-9]*)(\.[0-9]+)?$"
)
SHA256_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")
CURRENCY_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Z]{3}$")
FX_METHOD: Final[str] = (
    "multiply_source_currency_price_by_usd_per_source_currency_unit"
)
PRICE_PLACEHOLDERS: Final[frozenset[str]] = frozenset(
    {
        "placeholder",
        "todo",
        "tbd",
        "unknown",
        "n/a",
        "na",
        "not available",
        "not_available",
    }
)
GENERIC_LOCATORS: Final[frozenset[str]] = frozenset(
    {"官网", "控制台", "official website", "console", "website"}
)
CONDITION_DIMENSIONS: Final[frozenset[str]] = frozenset(
    {
        "flat",
        "tier",
        "context_length",
        "cache",
        "batch",
        "region",
        "call",
        "task",
        "extra_fee",
    }
)
UNSUPPORTED_DIMENSIONS: Final[frozenset[str]] = frozenset(
    {"call", "task", "extra_fee"}
)


def _fail(error_code: str, message: str) -> None:
    raise BatchRunnerError(error_code, message)


def _mapping(value: Any, error_code: str, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail(error_code, f"{label} must be a JSON object")
    return value


def _reject_extra_keys(
    value: Mapping[str, Any],
    allowed: set[str],
    error_code: str,
    label: str,
) -> None:
    if set(value) - allowed:
        _fail(error_code, f"{label} contains unsupported fields")


def _meaningful(value: Any, *, locator: bool = False) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    normalized = value.strip().casefold()
    if normalized in PRICE_PLACEHOLDERS:
        return False
    if locator and (
        normalized in GENERIC_LOCATORS or len(value.strip()) < 8
    ):
        return False
    return True


def _aware_timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        _fail("PRICE_TIMESTAMP_INVALID", "price timestamp is required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        _fail("PRICE_TIMESTAMP_INVALID", "price timestamp is not ISO-8601")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _fail("PRICE_TIMESTAMP_INVALID", "price timestamp must include timezone")
    return parsed


def _decimal_string(value: Any, *, fx: bool = False) -> Decimal:
    error_code = "FX_CONVERSION_INVALID" if fx else "PRICE_DECIMAL_INVALID"
    if not isinstance(value, str):
        _fail(error_code, "decimal value must be a JSON string")
    normalized = value.strip()
    if (
        normalized.casefold() in PRICE_PLACEHOLDERS
        or DECIMAL_STRING_PATTERN.fullmatch(normalized) is None
    ):
        _fail(error_code, "decimal value must be a finite non-negative plain string")
    try:
        parsed = Decimal(normalized)
    except InvalidOperation:
        _fail(error_code, "decimal value is invalid")
    if not parsed.is_finite() or parsed < 0 or (fx and parsed <= 0):
        _fail(error_code, "decimal value is outside the allowed range")
    return parsed


def _validate_source(value: Any) -> Mapping[str, Any]:
    source = _mapping(value, "PRICE_SOURCE_INVALID", "source")
    _reject_extra_keys(
        source,
        {"type", "title", "locator", "captured_at", "content_sha256"},
        "PRICE_SOURCE_INVALID",
        "source",
    )
    if source.get("type") not in ALLOWED_SOURCE_TYPES:
        _fail("PRICE_SOURCE_INVALID", "source.type is not approved")
    if not _meaningful(source.get("title")) or not _meaningful(
        source.get("locator"), locator=True
    ):
        _fail("PRICE_SOURCE_INVALID", "source title and locator are required")
    _aware_timestamp(source.get("captured_at"))
    content_hash = source.get("content_sha256")
    if not isinstance(content_hash, str) or SHA256_PATTERN.fullmatch(
        content_hash
    ) is None:
        _fail("PRICE_SOURCE_HASH_INVALID", "source content SHA-256 is invalid")
    return source


def _validate_conditions(value: Any) -> None:
    conditions = _mapping(value, "PRICE_TIER_AMBIGUOUS", "conditions")
    allowed = {
        "region",
        "billing_basis",
        "tier",
        "description",
        "applicability_confirmed",
        "pricing_dimensions",
        "selected_dimensions",
        "additional_fees",
    }
    _reject_extra_keys(
        conditions,
        allowed,
        "UNSUPPORTED_PRICE_COMPONENT",
        "conditions",
    )
    if conditions.get("region") != "cn-beijing":
        _fail("PRICE_TIER_AMBIGUOUS", "conditions.region is not frozen")
    if conditions.get("billing_basis") != "per_1m_input_output_tokens":
        _fail(
            "UNSUPPORTED_PRICE_COMPONENT",
            "billing basis cannot be represented by BudgetLedger",
        )
    if not _meaningful(conditions.get("tier")) or not _meaningful(
        conditions.get("description")
    ):
        _fail("PRICE_TIER_AMBIGUOUS", "conditions do not select one tier")
    if conditions.get("applicability_confirmed") is not True:
        _fail("PRICE_TIER_AMBIGUOUS", "price applicability is not confirmed")
    raw_dimensions = conditions.get("pricing_dimensions")
    if (
        not isinstance(raw_dimensions, list)
        or not raw_dimensions
        or any(not isinstance(item, str) for item in raw_dimensions)
    ):
        _fail("PRICE_TIER_AMBIGUOUS", "pricing dimensions are incomplete")
    dimensions = tuple(raw_dimensions)
    if len(set(dimensions)) != len(dimensions) or not set(
        dimensions
    ).issubset(CONDITION_DIMENSIONS):
        _fail("PRICE_TIER_AMBIGUOUS", "pricing dimensions are invalid")
    if set(dimensions) & UNSUPPORTED_DIMENSIONS:
        _fail(
            "UNSUPPORTED_PRICE_COMPONENT",
            "price includes a component BudgetLedger cannot represent",
        )
    if "flat" in dimensions and len(dimensions) != 1:
        _fail("PRICE_TIER_AMBIGUOUS", "flat and conditional tiers conflict")
    selected = _mapping(
        conditions.get("selected_dimensions"),
        "PRICE_TIER_AMBIGUOUS",
        "selected_dimensions",
    )
    allowed_selected = {"context_length", "cache", "batch", "region"}
    _reject_extra_keys(
        selected,
        allowed_selected,
        "PRICE_TIER_AMBIGUOUS",
        "selected_dimensions",
    )
    required_selection = set(dimensions) - {"flat", "tier"}
    for dimension in required_selection:
        if not _meaningful(selected.get(dimension)):
            _fail("PRICE_TIER_AMBIGUOUS", "applicable price tier is ambiguous")
    if "region" in required_selection and selected.get("region") != "cn-beijing":
        _fail("PRICE_TIER_AMBIGUOUS", "selected region conflicts with freeze")
    additional_fees = conditions.get("additional_fees", [])
    if not isinstance(additional_fees, list) or additional_fees:
        _fail(
            "UNSUPPORTED_PRICE_COMPONENT",
            "additional price component cannot be discarded",
        )


def _validate_model_price(value: Any) -> tuple[Decimal, Decimal]:
    model = _mapping(value, "PRICE_SNAPSHOT_INPUT_INVALID", "model price")
    allowed = {
        "input_per_million",
        "output_per_million",
        "conditions",
        "zero_price_confirmed",
        "zero_price_source_locator",
    }
    if set(model) - allowed:
        _fail(
            "UNSUPPORTED_PRICE_COMPONENT",
            "model price contains an unsupported price component",
        )
    try:
        input_price = _decimal_string(model["input_per_million"])
        output_price = _decimal_string(model["output_per_million"])
        conditions = model["conditions"]
    except KeyError:
        _fail("PRICE_SNAPSHOT_INPUT_INVALID", "model price fields are missing")
    _validate_conditions(conditions)
    if input_price == 0 or output_price == 0:
        if model.get("zero_price_confirmed") is not True or not _meaningful(
            model.get("zero_price_source_locator"), locator=True
        ):
            _fail(
                "ZERO_PRICE_PROVENANCE_REQUIRED",
                "zero price requires explicit official provenance",
            )
    return input_price, output_price


def _validate_fx(value: Any, currency: str) -> Decimal:
    if value is None:
        _fail("FX_SNAPSHOT_REQUIRED", "non-USD snapshot requires frozen FX")
    fx = _mapping(value, "FX_CONVERSION_INVALID", "fx")
    _reject_extra_keys(
        fx,
        {
            "from_currency",
            "to_currency",
            "usd_per_source_currency_unit",
            "source",
            "obtained_at",
            "method",
        },
        "FX_CONVERSION_INVALID",
        "fx",
    )
    if fx.get("from_currency") != currency or fx.get("to_currency") != "USD":
        _fail("FX_CONVERSION_INVALID", "FX currency direction is invalid")
    if fx.get("method") != FX_METHOD or not _meaningful(
        fx.get("source"), locator=True
    ):
        _fail("FX_CONVERSION_INVALID", "FX source or method is invalid")
    _aware_timestamp(fx.get("obtained_at"))
    return _decimal_string(fx.get("usd_per_source_currency_unit"), fx=True)


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


def normalize_price_snapshot_input(
    value: Mapping[str, Any],
    *,
    allow_test_input: bool = False,
) -> dict[str, Any]:
    """Validate provenance and return the existing runtime snapshot mapping."""

    root = _mapping(value, "PRICE_SNAPSHOT_INPUT_INVALID", "price snapshot")
    _reject_extra_keys(
        root,
        {
            "schema_version",
            "version",
            "obtained_at",
            "currency",
            "pricing_unit",
            "source",
            "models",
            "fx",
            "synthetic",
            "test_only",
        },
        "PRICE_SNAPSHOT_INPUT_INVALID",
        "price snapshot",
    )
    if root.get("schema_version") != PRICE_SNAPSHOT_INPUT_SCHEMA_VERSION:
        _fail("PRICE_SNAPSHOT_INPUT_INVALID", "schema_version is missing or invalid")
    if not _meaningful(root.get("version")):
        _fail("PRICE_SNAPSHOT_INPUT_INVALID", "version is required")
    obtained_at = root.get("obtained_at")
    _aware_timestamp(obtained_at)
    if root.get("pricing_unit") != "per_1m_tokens":
        _fail("PRICE_SNAPSHOT_INPUT_INVALID", "pricing_unit must be per_1m_tokens")
    currency = root.get("currency")
    if not isinstance(currency, str) or CURRENCY_PATTERN.fullmatch(currency) is None:
        _fail("PRICE_SNAPSHOT_INPUT_INVALID", "currency must be uppercase ISO 4217")
    if not allow_test_input and (
        root.get("synthetic") is True or root.get("test_only") is True
    ):
        _fail(
            "PRICE_SNAPSHOT_TEST_INPUT_REJECTED",
            "production CLI rejects synthetic or test-only price input",
        )
    source = _validate_source(root.get("source"))
    raw_models = _mapping(
        root.get("models"),
        "PRICE_MODEL_SET_MISMATCH",
        "models",
    )
    if set(raw_models) != set(FROZEN_PRICE_MODELS):
        _fail(
            "PRICE_MODEL_SET_MISMATCH",
            "models must exactly match the six frozen model names",
        )
    fx_rate = Decimal(1)
    if currency == "USD":
        if root.get("fx") is not None:
            _fail("FX_CONVERSION_INVALID", "USD snapshot must not apply FX")
    else:
        fx_rate = _validate_fx(root.get("fx"), currency)
    normalized_models: dict[str, dict[str, str]] = {}
    for model_name in FROZEN_PRICE_MODELS:
        input_price, output_price = _validate_model_price(raw_models[model_name])
        normalized_models[model_name] = {
            "input_per_million_usd": _decimal_text(input_price * fx_rate),
            "output_per_million_usd": _decimal_text(output_price * fx_rate),
        }
    source_reference = json.dumps(
        dict(source),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    normalized = {
        "version": str(root["version"]),
        "source": source_reference,
        "obtained_at": str(obtained_at),
        "models": normalized_models,
    }
    PriceSnapshot.from_mapping(normalized)
    return normalized


def load_price_snapshot_input(
    path: str | Path,
    *,
    allow_test_input: bool = False,
) -> dict[str, Any]:
    """Load UTF-8 JSON without reading configuration, environment, or network."""

    candidate = Path(path)
    try:
        raw = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BatchRunnerError(
            "PRICE_SNAPSHOT_INPUT_INVALID",
            "operator price snapshot is not valid UTF-8 JSON",
        ) from exc
    if not isinstance(raw, Mapping):
        _fail("PRICE_SNAPSHOT_INPUT_INVALID", "price snapshot must be an object")
    return normalize_price_snapshot_input(raw, allow_test_input=allow_test_input)


def inspect_price_snapshot_schema(
    schema: Mapping[str, Any],
    frozen_config: Mapping[str, Any],
) -> dict[str, object]:
    """Perform a dependency-free structural self-check of the JSON Schema."""

    definitions = schema.get("$defs")
    properties = schema.get("properties")
    if not isinstance(definitions, Mapping) or not isinstance(properties, Mapping):
        _fail("PRICE_SNAPSHOT_SPEC_INVALID", "price input schema is incomplete")
    decimal_rule = definitions.get("decimalString")
    time_rule = definitions.get("timezoneDateTime")
    source_rule = definitions.get("source")
    fx_rule = definitions.get("fx")
    model_rule = definitions.get("models")
    provider = frozen_config.get("provider")
    config_models = provider.get("models") if isinstance(provider, Mapping) else None
    frozen_values = (
        set(config_models.values()) if isinstance(config_models, Mapping) else set()
    )
    source_required = (
        set(source_rule.get("required", ())) if isinstance(source_rule, Mapping) else set()
    )
    fx_required = (
        set(fx_rule.get("required", ())) if isinstance(fx_rule, Mapping) else set()
    )
    schema_models = (
        set(model_rule.get("required", ())) if isinstance(model_rule, Mapping) else set()
    )
    checks: dict[str, object] = {
        "spec_schema_valid": (
            schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema"
            and properties.get("schema_version", {}).get("const")
            == PRICE_SNAPSHOT_INPUT_SCHEMA_VERSION
            and schema_models == set(FROZEN_PRICE_MODELS)
        ),
        "required_models": len(FROZEN_PRICE_MODELS),
        "model_set_matches_frozen_config": frozen_values
        == set(FROZEN_PRICE_MODELS),
        "decimal_rules_present": (
            isinstance(decimal_rule, Mapping)
            and decimal_rule.get("pattern") == DECIMAL_STRING_PATTERN.pattern
        ),
        "timezone_rules_present": (
            isinstance(time_rule, Mapping)
            and time_rule.get("format") == "date-time"
            and bool(time_rule.get("pattern"))
        ),
        "source_provenance_rules_present": source_required
        == {"type", "title", "locator", "captured_at", "content_sha256"},
        "fx_rules_present": fx_required
        == {
            "from_currency",
            "to_currency",
            "usd_per_source_currency_unit",
            "source",
            "obtained_at",
            "method",
        },
        "actual_price_snapshot_supplied": False,
        "actual_price_snapshot_validated": False,
        "provider_calls": 0,
        "provider_preflight_executed": False,
    }
    required_true = (
        "spec_schema_valid",
        "model_set_matches_frozen_config",
        "decimal_rules_present",
        "timezone_rules_present",
        "source_provenance_rules_present",
        "fx_rules_present",
    )
    if not all(checks[name] is True for name in required_true):
        _fail("PRICE_SNAPSHOT_SPEC_INVALID", "price input schema self-check failed")
    return checks
