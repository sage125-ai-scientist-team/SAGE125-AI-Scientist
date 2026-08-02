"""Secret-free actual provider-call audit and fail-closed budget accounting."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Final, Mapping

from app.batch.errors import BatchRunnerError


SHA256: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")
SANITIZED_REQUEST_ID: Final[re.Pattern[str]] = re.compile(
    r"^req_sha256:[0-9a-f]{64}$"
)
MILLION: Final[Decimal] = Decimal(1_000_000)


def sanitize_request_id(raw_request_id: str) -> str:
    """Irreversibly sanitize a provider request identifier for repository audit."""

    if not isinstance(raw_request_id, str) or not raw_request_id.strip():
        raise BatchRunnerError(
            "REQUEST_ID_MISSING",
            "provider preflight returned no request identifier",
        )
    return "req_sha256:" + hashlib.sha256(raw_request_id.encode("utf-8")).hexdigest()


def _decimal(value: Any, field_name: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a decimal") from exc
    if not parsed.is_finite() or parsed < 0:
        raise ValueError(f"{field_name} must be finite and non-negative")
    return parsed


def _aware(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


@dataclass(frozen=True, slots=True)
class ModelPrice:
    input_per_million_usd: Decimal
    output_per_million_usd: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "input_per_million_usd",
            _decimal(self.input_per_million_usd, "input_per_million_usd"),
        )
        object.__setattr__(
            self,
            "output_per_million_usd",
            _decimal(self.output_per_million_usd, "output_per_million_usd"),
        )


@dataclass(frozen=True, slots=True)
class PriceSnapshot:
    version: str
    source: str
    obtained_at: datetime
    models: Mapping[str, ModelPrice]

    def __post_init__(self) -> None:
        if not self.version.strip() or not self.source.strip():
            raise ValueError("price snapshot version and source are required")
        _aware(self.obtained_at, "obtained_at")
        normalized = dict(self.models)
        if not normalized or any(
            not name.strip() or not isinstance(price, ModelPrice)
            for name, price in normalized.items()
        ):
            raise ValueError("price snapshot requires named model prices")
        object.__setattr__(self, "models", normalized)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "PriceSnapshot":
        try:
            raw_models = value["models"]
            if not isinstance(raw_models, Mapping):
                raise TypeError("models must be an object")
            models = {
                str(name): ModelPrice(
                    input_per_million_usd=_decimal(
                        price["input_per_million_usd"],
                        "input_per_million_usd",
                    ),
                    output_per_million_usd=_decimal(
                        price["output_per_million_usd"],
                        "output_per_million_usd",
                    ),
                )
                for name, price in raw_models.items()
                if isinstance(price, Mapping)
            }
            return cls(
                version=str(value["version"]),
                source=str(value["source"]),
                obtained_at=datetime.fromisoformat(str(value["obtained_at"])),
                models=models,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise BatchRunnerError(
                "PRICE_SNAPSHOT_INVALID",
                (
                    "price snapshot must contain version, source, obtained_at, "
                    "and model prices"
                ),
            ) from exc


@dataclass(frozen=True, slots=True)
class ActualCallAudit:
    provider: str
    model: str
    route_tier: str
    request_timestamp: datetime
    sanitized_request_id: str
    static_prompt_version: str
    static_prompt_hash: str
    dynamic_prompt_hash: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: Decimal | None
    settled_cost_usd: Decimal | None
    retry_attempt: int
    fallback: bool
    price_snapshot_version: str | None

    def __post_init__(self) -> None:
        required = (
            self.provider,
            self.model,
            self.route_tier,
            self.static_prompt_version,
        )
        if any(not value.strip() for value in required):
            raise ValueError("call audit text fields must not be empty")
        _aware(self.request_timestamp, "request_timestamp")
        if not SANITIZED_REQUEST_ID.fullmatch(self.sanitized_request_id):
            raise ValueError("request ID must be a sanitized SHA-256 identifier")
        for field_name, value in (
            ("static_prompt_hash", self.static_prompt_hash),
            ("dynamic_prompt_hash", self.dynamic_prompt_hash),
        ):
            if not SHA256.fullmatch(value):
                raise ValueError(f"{field_name} must be lowercase SHA-256")
        if min(self.input_tokens, self.output_tokens, self.total_tokens) < 0:
            raise ValueError("token counts must be non-negative")
        if self.total_tokens != self.input_tokens + self.output_tokens:
            raise ValueError("total_tokens must equal input_tokens + output_tokens")
        if self.retry_attempt < 1:
            raise ValueError("retry_attempt must be positive")
        if type(self.fallback) is not bool:
            raise ValueError("fallback must be a boolean")
        for field_name in ("estimated_cost_usd", "settled_cost_usd"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, _decimal(value, field_name))
        if self.price_snapshot_version is not None and not (
            self.price_snapshot_version.strip()
        ):
            raise ValueError("price_snapshot_version cannot be blank")

    @property
    def accounted_cost_usd(self) -> Decimal | None:
        return (
            self.settled_cost_usd
            if self.settled_cost_usd is not None
            else self.estimated_cost_usd
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "route_tier": self.route_tier,
            "request_timestamp": self.request_timestamp.isoformat(),
            "sanitized_request_id": self.sanitized_request_id,
            "static_prompt_version": self.static_prompt_version,
            "static_prompt_hash": self.static_prompt_hash,
            "dynamic_prompt_hash": self.dynamic_prompt_hash,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": (
                None
                if self.estimated_cost_usd is None
                else str(self.estimated_cost_usd)
            ),
            "settled_cost_usd": (
                None
                if self.settled_cost_usd is None
                else str(self.settled_cost_usd)
            ),
            "retry_attempt": self.retry_attempt,
            "fallback": self.fallback,
            "price_snapshot_version": self.price_snapshot_version,
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ActualCallAudit":
        try:
            return cls(
                provider=str(value["provider"]),
                model=str(value["model"]),
                route_tier=str(value["route_tier"]),
                request_timestamp=datetime.fromisoformat(
                    str(value["request_timestamp"])
                ),
                sanitized_request_id=str(value["sanitized_request_id"]),
                static_prompt_version=str(value["static_prompt_version"]),
                static_prompt_hash=str(value["static_prompt_hash"]),
                dynamic_prompt_hash=str(value["dynamic_prompt_hash"]),
                input_tokens=int(value["input_tokens"]),
                output_tokens=int(value["output_tokens"]),
                total_tokens=int(value["total_tokens"]),
                estimated_cost_usd=(
                    None
                    if value.get("estimated_cost_usd") is None
                    else _decimal(
                        value["estimated_cost_usd"], "estimated_cost_usd"
                    )
                ),
                settled_cost_usd=(
                    None
                    if value.get("settled_cost_usd") is None
                    else _decimal(value["settled_cost_usd"], "settled_cost_usd")
                ),
                retry_attempt=int(value["retry_attempt"]),
                fallback=value["fallback"],
                price_snapshot_version=(
                    None
                    if value.get("price_snapshot_version") is None
                    else str(value["price_snapshot_version"])
                ),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise BatchRunnerError(
                "LLM_CALL_AUDIT_INVALID",
                "llm_call_audit.json is not a valid secret-free audit record",
            ) from exc

    @classmethod
    def from_json(cls, payload: str) -> "ActualCallAudit":
        try:
            raw = json.loads(payload)
            if not isinstance(raw, Mapping):
                raise TypeError("audit must be an object")
        except (json.JSONDecodeError, TypeError) as exc:
            raise BatchRunnerError(
                "LLM_CALL_AUDIT_INVALID",
                "llm_call_audit.json must be a JSON object",
            ) from exc
        return cls.from_mapping(raw)


def compute_estimated_cost(
    snapshot: PriceSnapshot,
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> Decimal:
    """Estimate with an injected frozen price snapshot; never guess a price."""

    if input_tokens < 0 or output_tokens < 0:
        raise ValueError("token counts must be non-negative")
    price = snapshot.models.get(model)
    if price is None:
        raise BatchRunnerError(
            "UNKNOWN_COST",
            f"No frozen price exists for model {model!r}",
        )
    return (
        Decimal(input_tokens) * price.input_per_million_usd
        + Decimal(output_tokens) * price.output_per_million_usd
    ) / MILLION


def validate_actual_call_audit(audit: ActualCallAudit) -> None:
    """Reject fallback calls and any call whose cost cannot be accounted."""

    if not isinstance(audit, ActualCallAudit):
        raise TypeError("audit must be ActualCallAudit")
    if audit.fallback:
        raise BatchRunnerError(
            "FALLBACK_NOT_ALLOWED",
            "formal WB5 calls must use the frozen provider/model without fallback",
        )
    if audit.accounted_cost_usd is None:
        raise BatchRunnerError(
            "UNKNOWN_COST",
            "formal WB5 calls cannot continue with unknown cost",
        )
    if audit.estimated_cost_usd is not None and not audit.price_snapshot_version:
        raise BatchRunnerError(
            "PRICE_SNAPSHOT_REQUIRED",
            "estimated provider cost requires a frozen price snapshot version",
        )


@dataclass(slots=True)
class BudgetLedger:
    """Two-level Decimal ledger with retry accumulation and resume idempotency."""

    per_question_token_limit: int
    per_question_cost_limit_usd: Decimal
    batch_token_limit: int
    batch_cost_limit_usd: Decimal
    max_output_tokens_per_call: int
    _audits: dict[str, tuple[str, ActualCallAudit]] = field(default_factory=dict)
    _question_tokens: dict[str, int] = field(default_factory=dict)
    _question_costs: dict[str, Decimal] = field(default_factory=dict)
    batch_tokens: int = 0
    batch_cost_usd: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        if min(
            self.per_question_token_limit,
            self.batch_token_limit,
            self.max_output_tokens_per_call,
        ) < 0:
            raise ValueError("token limits must be non-negative")
        self.per_question_cost_limit_usd = _decimal(
            self.per_question_cost_limit_usd,
            "per_question_cost_limit_usd",
        )
        self.batch_cost_limit_usd = _decimal(
            self.batch_cost_limit_usd,
            "batch_cost_limit_usd",
        )

    def question_tokens(self, question_id: str) -> int:
        return self._question_tokens.get(question_id, 0)

    def question_cost_usd(self, question_id: str) -> Decimal:
        return self._question_costs.get(question_id, Decimal("0"))

    def require_capacity(
        self,
        question_id: str,
        *,
        planned_input_tokens: int,
        planned_output_tokens: int,
        estimated_cost_usd: Decimal | None,
    ) -> None:
        if not question_id.strip():
            raise ValueError("question_id must not be empty")
        if planned_input_tokens < 0 or planned_output_tokens < 0:
            raise ValueError("planned token counts must be non-negative")
        if planned_output_tokens > self.max_output_tokens_per_call:
            raise BatchRunnerError(
                "BUDGET_EXHAUSTED",
                "planned output exceeds the frozen per-call maximum",
            )
        if estimated_cost_usd is None:
            raise BatchRunnerError(
                "UNKNOWN_COST",
                "a frozen cost estimate is required before the next provider call",
            )
        cost = _decimal(estimated_cost_usd, "estimated_cost_usd")
        tokens = planned_input_tokens + planned_output_tokens
        if (
            self.question_tokens(question_id) + tokens
            > self.per_question_token_limit
            or self.batch_tokens + tokens > self.batch_token_limit
            or self.question_cost_usd(question_id) + cost
            > self.per_question_cost_limit_usd
            or self.batch_cost_usd + cost > self.batch_cost_limit_usd
        ):
            raise BatchRunnerError(
                "BUDGET_EXHAUSTED",
                "the next provider call would exceed a frozen question or batch budget",
            )

    def record_call(self, question_id: str, audit: ActualCallAudit) -> bool:
        validate_actual_call_audit(audit)
        prior = self._audits.get(audit.sanitized_request_id)
        if prior is not None:
            if prior == (question_id, audit):
                return False
            raise BatchRunnerError(
                "AUDIT_REQUEST_ID_COLLISION",
                "a sanitized request ID cannot identify two different calls",
            )
        cost = audit.accounted_cost_usd
        assert cost is not None
        self.require_capacity(
            question_id,
            planned_input_tokens=audit.input_tokens,
            planned_output_tokens=audit.output_tokens,
            estimated_cost_usd=cost,
        )
        self._audits[audit.sanitized_request_id] = (question_id, audit)
        self._question_tokens[question_id] = (
            self.question_tokens(question_id) + audit.total_tokens
        )
        self._question_costs[question_id] = self.question_cost_usd(question_id) + cost
        self.batch_tokens += audit.total_tokens
        self.batch_cost_usd += cost
        return True
