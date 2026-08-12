"""Offline contract tests for the T07-WB5 operator price snapshot input."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from app.batch.actual_call_audit import PriceSnapshot
from app.batch.errors import BatchRunnerError
from app.batch.price_snapshot_input import (
    FROZEN_PRICE_MODELS,
    PRICE_SNAPSHOT_INPUT_SCHEMA_VERSION,
    load_price_snapshot_input,
    normalize_price_snapshot_input,
)
from scripts.batch_125.validate_price_snapshot import main


REPO_ROOT = Path(__file__).resolve().parents[2]


def _conditions() -> dict[str, object]:
    return {
        "region": "cn-beijing",
        "billing_basis": "per_1m_input_output_tokens",
        "tier": "synthetic-flat-test-tier",
        "description": "Synthetic flat-rate test fixture only.",
        "applicability_confirmed": True,
        "pricing_dimensions": ["flat"],
        "selected_dimensions": {},
    }


def _valid_input(currency: str = "USD") -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": PRICE_SNAPSHOT_INPUT_SCHEMA_VERSION,
        "version": "synthetic-prices-v1",
        "obtained_at": "2026-08-06T01:02:03+08:00",
        "currency": currency,
        "pricing_unit": "per_1m_tokens",
        "source": {
            "type": "captain_material",
            "title": "Synthetic price fixture for contract tests",
            "locator": "test-fixture://price-snapshot/source-v1",
            "captured_at": "2026-08-06T01:00:00+08:00",
            "content_sha256": "a" * 64,
        },
        "models": {
            model: {
                "input_per_million": "1.25",
                "output_per_million": "2.50",
                "conditions": _conditions(),
            }
            for model in FROZEN_PRICE_MODELS
        },
        "synthetic": True,
        "test_only": True,
    }
    if currency != "USD":
        payload["fx"] = {
            "from_currency": currency,
            "to_currency": "USD",
            "usd_per_source_currency_unit": "0.125",
            "source": "test-fixture://fx/source-v1",
            "obtained_at": "2026-08-06T01:01:00+08:00",
            "method": (
                "multiply_source_currency_price_by_"
                "usd_per_source_currency_unit"
            ),
        }
    return payload


def _assert_error(payload: dict[str, object], code: str) -> None:
    with pytest.raises(BatchRunnerError) as captured:
        normalize_price_snapshot_input(payload, allow_test_input=True)
    assert captured.value.error_code == code


def test_valid_usd_synthetic_fixture_normalizes_for_runtime() -> None:
    normalized = normalize_price_snapshot_input(
        _valid_input(), allow_test_input=True
    )

    snapshot = PriceSnapshot.from_mapping(normalized)

    assert tuple(snapshot.models) == FROZEN_PRICE_MODELS
    assert snapshot.models["qwen3.6-flash"].input_per_million_usd == Decimal(
        "1.25"
    )


def test_valid_cny_fx_synthetic_fixture_uses_decimal_only() -> None:
    normalized = normalize_price_snapshot_input(
        _valid_input("CNY"), allow_test_input=True
    )

    snapshot = PriceSnapshot.from_mapping(normalized)

    assert snapshot.models["qwen3.7-max"].input_per_million_usd == Decimal(
        "0.15625"
    )
    assert snapshot.models["qwen3.7-max"].output_per_million_usd == Decimal(
        "0.31250"
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", None),
        ("version", None),
        ("version", ""),
    ],
    ids=["missing-schema-version", "missing-version", "empty-version"],
)
def test_required_identity_fields_fail_closed(
    field: str, value: object
) -> None:
    payload = _valid_input()
    if value is None:
        payload.pop(field)
    else:
        payload[field] = value
    _assert_error(payload, "PRICE_SNAPSHOT_INPUT_INVALID")


def test_obtained_at_requires_timezone() -> None:
    payload = _valid_input()
    payload["obtained_at"] = "2026-08-06T01:02:03"
    _assert_error(payload, "PRICE_TIMESTAMP_INVALID")


def test_source_captured_at_requires_timezone() -> None:
    payload = _valid_input()
    payload["source"]["captured_at"] = "2026-08-06T01:02:03"  # type: ignore[index]
    _assert_error(payload, "PRICE_TIMESTAMP_INVALID")


def test_source_content_hash_must_be_lowercase_sha256() -> None:
    payload = _valid_input()
    payload["source"]["content_sha256"] = "BAD"  # type: ignore[index]
    _assert_error(payload, "PRICE_SOURCE_HASH_INVALID")


@pytest.mark.parametrize(
    ("field", "value"),
    [("type", "web_search"), ("locator", "")],
)
def test_source_type_and_locator_are_restricted(
    field: str, value: str
) -> None:
    payload = _valid_input()
    payload["source"][field] = value  # type: ignore[index]
    _assert_error(payload, "PRICE_SOURCE_INVALID")


def test_missing_frozen_model_is_rejected() -> None:
    payload = _valid_input()
    payload["models"].pop("qwen3-rerank")  # type: ignore[union-attr]
    _assert_error(payload, "PRICE_MODEL_SET_MISMATCH")


def test_extra_model_is_rejected() -> None:
    payload = _valid_input()
    payload["models"]["alias-model"] = {  # type: ignore[index]
        "input_per_million": "1.00",
        "output_per_million": "1.00",
        "conditions": _conditions(),
    }
    _assert_error(payload, "PRICE_MODEL_SET_MISMATCH")


@pytest.mark.parametrize(
    "value",
    [1.25, "not-a-decimal", "NaN", "Infinity", "-1", "1e-3"],
    ids=["not-string", "invalid", "nan", "infinity", "negative", "scientific"],
)
def test_invalid_decimal_prices_are_rejected(value: object) -> None:
    payload = _valid_input()
    payload["models"]["qwen3.6-flash"]["input_per_million"] = value  # type: ignore[index]
    _assert_error(payload, "PRICE_DECIMAL_INVALID")


@pytest.mark.parametrize("value", ["placeholder", "TODO", "unknown", "N/A"])
def test_placeholder_prices_are_rejected(value: str) -> None:
    payload = _valid_input()
    payload["models"]["qwen3.6-flash"]["output_per_million"] = value  # type: ignore[index]
    _assert_error(payload, "PRICE_DECIMAL_INVALID")


def test_unknown_price_cannot_be_written_as_zero() -> None:
    payload = _valid_input()
    payload["models"]["qwen3.6-flash"]["input_per_million"] = "0"  # type: ignore[index]
    _assert_error(payload, "ZERO_PRICE_PROVENANCE_REQUIRED")


def test_confirmed_official_zero_requires_explicit_locator() -> None:
    payload = _valid_input()
    model = payload["models"]["qwen3.6-flash"]  # type: ignore[index]
    model["input_per_million"] = "0"
    model["zero_price_confirmed"] = True
    model["zero_price_source_locator"] = "official-test://zero-price-row"

    normalized = normalize_price_snapshot_input(payload, allow_test_input=True)

    assert normalized["models"]["qwen3.6-flash"]["input_per_million_usd"] == "0"  # type: ignore[index]


def test_non_usd_requires_fx_snapshot() -> None:
    payload = _valid_input("CNY")
    payload.pop("fx")
    _assert_error(payload, "FX_SNAPSHOT_REQUIRED")


def test_fx_direction_is_fixed_to_usd() -> None:
    payload = _valid_input("CNY")
    payload["fx"]["to_currency"] = "CNY"  # type: ignore[index]
    _assert_error(payload, "FX_CONVERSION_INVALID")


def test_fx_timestamp_requires_timezone() -> None:
    payload = _valid_input("CNY")
    payload["fx"]["obtained_at"] = "2026-08-06T01:02:03"  # type: ignore[index]
    _assert_error(payload, "PRICE_TIMESTAMP_INVALID")


def test_fx_decimal_must_be_positive_plain_string() -> None:
    payload = _valid_input("CNY")
    payload["fx"]["usd_per_source_currency_unit"] = "NaN"  # type: ignore[index]
    _assert_error(payload, "FX_CONVERSION_INVALID")


def test_tier_dimensions_must_select_one_applicable_tier() -> None:
    payload = _valid_input()
    conditions = payload["models"]["qwen3.6-flash"]["conditions"]  # type: ignore[index]
    conditions["pricing_dimensions"] = ["context_length"]
    conditions["selected_dimensions"] = {}
    _assert_error(payload, "PRICE_TIER_AMBIGUOUS")


def test_unrepresentable_extra_fee_is_rejected() -> None:
    payload = _valid_input()
    payload["models"]["qwen3.6-flash"]["per_request_fee"] = "1.00"  # type: ignore[index]
    _assert_error(payload, "UNSUPPORTED_PRICE_COMPONENT")


def test_normalized_mapping_is_accepted_by_price_snapshot() -> None:
    normalized = normalize_price_snapshot_input(
        _valid_input(), allow_test_input=True
    )
    assert isinstance(PriceSnapshot.from_mapping(normalized), PriceSnapshot)


def test_loading_never_reads_dotenv(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "synthetic-prices.json"
    source.write_text(json.dumps(_valid_input()), encoding="utf-8")
    original = Path.read_text

    def guarded(path: Path, *args, **kwargs):
        if path.name == ".env":
            raise AssertionError("validator attempted to read .env")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded)

    loaded = load_price_snapshot_input(source, allow_test_input=True)

    assert loaded["version"] == "synthetic-prices-v1"


def test_production_cli_rejects_synthetic_and_test_only(
    tmp_path: Path, capsys
) -> None:
    source = tmp_path / "synthetic-prices.json"
    source.write_text(json.dumps(_valid_input()), encoding="utf-8")

    exit_code = main(["--input", str(source), "--repo-root", str(REPO_ROOT)])
    output = capsys.readouterr().out

    assert exit_code == 2
    assert "PRICE_SNAPSHOT_TEST_INPUT_REJECTED" in output
    assert "1.25" not in output


def test_default_cli_summary_has_no_prices_or_account_locator(
    tmp_path: Path, capsys
) -> None:
    payload = _valid_input()
    payload["synthetic"] = False
    payload["test_only"] = False
    payload["source"]["locator"] = "account-test://private-account-123"  # type: ignore[index]
    source = tmp_path / "operator-prices.json"
    source.write_text(json.dumps(payload), encoding="utf-8")

    exit_code = main(["--input", str(source), "--repo-root", str(REPO_ROOT)])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "actual_price_snapshot_validated" in output
    assert "1.25" not in output
    assert "private-account-123" not in output
    assert "provider_calls" in output


def test_repository_internal_normalized_output_is_rejected(
    tmp_path: Path, capsys
) -> None:
    payload = _valid_input()
    payload["synthetic"] = False
    payload["test_only"] = False
    source = tmp_path / "operator-prices.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    blocked = REPO_ROOT / "must-not-write-price-snapshot.json"

    exit_code = main(
        [
            "--input",
            str(source),
            "--normalized-output",
            str(blocked),
            "--repo-root",
            str(REPO_ROOT),
        ]
    )

    assert exit_code == 2
    assert "PRICE_SNAPSHOT_OUTPUT_PATH_INVALID" in capsys.readouterr().out
    assert not blocked.exists()


def test_self_check_is_offline_and_reports_no_actual_snapshot(capsys) -> None:
    exit_code = main(["--self-check", "--repo-root", str(REPO_ROOT)])
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output == {
        "actual_price_snapshot_supplied": False,
        "actual_price_snapshot_validated": False,
        "decimal_rules_present": True,
        "fx_rules_present": True,
        "model_set_matches_frozen_config": True,
        "provider_calls": 0,
        "provider_preflight_executed": False,
        "required_models": 6,
        "source_provenance_rules_present": True,
        "spec_schema_valid": True,
        "timezone_rules_present": True,
    }
