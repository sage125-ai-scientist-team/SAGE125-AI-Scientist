"""Offline, fail-closed preflight for the frozen T07-WB5 five-question run."""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Final

from app.batch.errors import BatchRunnerError
from app.contracts.batch import (
    BATCH_SCHEMA_VERSION,
    BATCH_SCHEMA_VERSION_V2,
    CHECKPOINT_SCHEMA_VERSION,
    CHECKPOINT_SCHEMA_VERSION_V2,
    TOKEN_AND_COST_BUDGET_POLICY_VERSION,
    TOKEN_ONLY_BUDGET_POLICY_VERSION,
    BudgetMode,
    BudgetPolicy,
)


FROZEN_QUESTION_IDS: Final[tuple[str, ...]] = (
    "Q001",
    "Q028",
    "Q050",
    "Q075",
    "Q107",
)
EXPECTED_QUESTION_COUNT: Final[int] = 125
SHA256_LENGTH: Final[int] = 64
RAW_BYTES_SHA256: Final[str] = "raw_bytes_sha256"
UTF8_LF_NORMALIZED_TEXT_SHA256: Final[str] = (
    "utf8_lf_normalized_text_sha256"
)
SUPPORTED_HASH_MODES: Final[frozenset[str]] = frozenset(
    {RAW_BYTES_SHA256, UTF8_LF_NORMALIZED_TEXT_SHA256}
)
APPROVED_TOKEN_ONLY_FREEZE_ID: Final[str] = "T07-WB5-20260807-v2"
CAPTAIN_OPTION_B_REFERENCE: Final[str] = (
    "captain-option-b-approved-2026-08-07"
)


@dataclass(frozen=True, slots=True)
class PreflightIssue:
    code: str
    message: str

    def __post_init__(self) -> None:
        if not self.code.strip() or not self.message.strip():
            raise ValueError("preflight issue code and message are required")


@dataclass(frozen=True, slots=True)
class FrozenFileRecord:
    path: str
    size: int | None
    sha256: str
    name: str | None = None
    hash_mode: str = RAW_BYTES_SHA256

    def __post_init__(self) -> None:
        if not self.path.strip():
            raise ValueError("frozen file path must not be empty")
        if self.size is not None and self.size < 0:
            raise ValueError("frozen file size must be non-negative")
        if not _is_sha256(self.sha256):
            raise ValueError("frozen file sha256 must be lowercase SHA-256")
        if self.hash_mode not in SUPPORTED_HASH_MODES:
            raise ValueError(f"unsupported frozen file hash mode: {self.hash_mode}")


@dataclass(frozen=True, slots=True)
class FrozenQuestionRecord:
    question_id: str
    domain: str | None
    question: str | None
    canonical_input_hash: str | None
    mapping_status: str

    def __post_init__(self) -> None:
        if not self.question_id.strip() or not self.mapping_status.strip():
            raise ValueError("frozen question identity and mapping status are required")
        if self.canonical_input_hash is not None and not _is_sha256(
            self.canonical_input_hash
        ):
            raise ValueError("canonical_input_hash must be lowercase SHA-256")


@dataclass(frozen=True, slots=True)
class FrozenFiveRunConfig:
    freeze_id: str
    frozen_at: str
    source_kind: str
    authoritative_pdf: FrozenFileRecord
    production_question_source: FrozenFileRecord
    question_id_field: str
    questions: tuple[FrozenQuestionRecord, ...]
    provider_name: str
    route_id: str
    models: Mapping[str, str]
    model_version: str
    provider_environment_variables: tuple[str, ...]
    prompt_version: str
    prompt_file: FrozenFileRecord
    batch_schema: str
    checkpoint_schema: str
    schema_files: tuple[FrozenFileRecord, ...]
    approved_t01_commit: str
    t01_public_interface: str
    t03_public_interfaces: tuple[str, ...]
    budget_policy: BudgetPolicy
    budgets: Mapping[str, Any]
    price_snapshot: Mapping[str, Any] | None

    @property
    def budget_policy_version(self) -> str:
        return self.budget_policy.version

    @property
    def budget_mode(self) -> BudgetMode:
        return self.budget_policy.mode

    @property
    def cost_accounting_required(self) -> bool:
        return self.budget_policy.cost_accounting_required

    @property
    def price_snapshot_required(self) -> bool:
        return self.budget_policy.price_snapshot_required


@dataclass(frozen=True, slots=True)
class SourceProvenanceResult:
    issues: tuple[PreflightIssue, ...]

    @property
    def passed(self) -> bool:
        return not self.issues

    @property
    def error_codes(self) -> tuple[str, ...]:
        return tuple(issue.code for issue in self.issues)


@dataclass(frozen=True, slots=True)
class GateAvailabilityResult:
    available: bool
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class FiveRunPreflightResult:
    status: str
    issues: tuple[PreflightIssue, ...]
    source_provenance: SourceProvenanceResult
    provider_configured: bool
    t01: GateAvailabilityResult
    t03: GateAvailabilityResult
    budget_policy_version: str
    budget_mode: BudgetMode
    cost_accounting_required: bool
    price_snapshot_required: bool
    provider_preflight_executed: bool = False
    provider_calls: int = 0

    @property
    def passed(self) -> bool:
        return self.status == "FIVE_REAL_RUNS_READY_FOR_PROVIDER_PREFLIGHT"

    @property
    def error_codes(self) -> tuple[str, ...]:
        return tuple(issue.code for issue in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "error_codes": list(self.error_codes),
            "issues": [
                {"code": issue.code, "message": issue.message}
                for issue in self.issues
            ],
            "source_provenance_verified": self.source_provenance.passed,
            "provider_configured": self.provider_configured,
            "t01": {
                "available": self.t01.available,
                "code": self.t01.code,
            },
            "t03": {
                "available": self.t03.available,
                "code": self.t03.code,
            },
            "provider_preflight_executed": self.provider_preflight_executed,
            "provider_calls": self.provider_calls,
            "budget_policy_version": self.budget_policy_version,
            "budget_mode": self.budget_mode.value,
            "cost_accounting_required": self.cost_accounting_required,
            "price_snapshot_required": self.price_snapshot_required,
        }


GitRunner = Callable[
    [tuple[str, ...], Path], subprocess.CompletedProcess[str]
]


def _is_sha256(value: str) -> bool:
    return (
        len(value) == SHA256_LENGTH
        and value == value.lower()
        and all(character in "0123456789abcdef" for character in value)
    )


def _as_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise BatchRunnerError(
            "FROZEN_CONFIG_INVALID",
            f"{label} must be a JSON object",
        )
    return value


def _file_record(value: Any, label: str) -> FrozenFileRecord:
    raw = _as_mapping(value, label)
    try:
        size = raw.get("size")
        return FrozenFileRecord(
            name=None if raw.get("name") is None else str(raw["name"]),
            path=str(raw["path"]),
            size=None if size is None else int(size),
            sha256=str(raw["sha256"]),
            hash_mode=str(raw.get("hash_mode") or RAW_BYTES_SHA256),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise BatchRunnerError(
            "FROZEN_CONFIG_INVALID",
            f"{label} requires path, size, and sha256",
        ) from exc


def _budget_policy(
    root: Mapping[str, Any],
    *,
    freeze_id: str,
    batch_schema: str,
    checkpoint_schema: str,
) -> BudgetPolicy:
    raw = root.get("budget_policy")
    if raw is None:
        if (
            batch_schema != BATCH_SCHEMA_VERSION
            or checkpoint_schema != CHECKPOINT_SCHEMA_VERSION
        ):
            raise ValueError("legacy budget policy requires v1 schemas")
        return BudgetPolicy(
            version=TOKEN_AND_COST_BUDGET_POLICY_VERSION,
            mode=BudgetMode.TOKEN_AND_COST,
            cost_accounting_required=True,
            price_snapshot_required=True,
        )
    policy = BudgetPolicy.model_validate(_as_mapping(raw, "budget_policy"))
    if policy.mode is BudgetMode.TOKEN_ONLY:
        if (
            freeze_id != APPROVED_TOKEN_ONLY_FREEZE_ID
            or batch_schema != BATCH_SCHEMA_VERSION_V2
            or checkpoint_schema != CHECKPOINT_SCHEMA_VERSION_V2
            or policy.version != TOKEN_ONLY_BUDGET_POLICY_VERSION
            or policy.captain_waiver_reference != CAPTAIN_OPTION_B_REFERENCE
        ):
            raise ValueError("token_only policy is not the approved WB5 v2 freeze")
    elif (
        batch_schema != BATCH_SCHEMA_VERSION
        or checkpoint_schema != CHECKPOINT_SCHEMA_VERSION
    ):
        raise ValueError("token_and_cost policy requires v1 schemas")
    return policy


def _validate_budgets(
    budgets: Mapping[str, Any],
    policy: BudgetPolicy,
) -> None:
    per_question = _as_mapping(budgets.get("per_question"), "budgets.per_question")
    batch = _as_mapping(budgets.get("batch"), "budgets.batch")
    for label, scope in (("per_question", per_question), ("batch", batch)):
        token_limit = scope.get("token_limit")
        if type(token_limit) is not int or token_limit < 0:
            raise ValueError(f"{label} token_limit must be non-negative")
    maximum = budgets.get("max_output_tokens_per_call")
    if type(maximum) is not int or maximum < 0:
        raise ValueError("max_output_tokens_per_call must be non-negative")
    cost_fields = (
        per_question.get("cost_limit_usd"),
        batch.get("cost_limit_usd"),
    )
    if policy.mode is BudgetMode.TOKEN_ONLY:
        if any(value is not None for value in cost_fields):
            raise ValueError("token_only freeze cannot contain cost limits")
    elif any(value is None for value in cost_fields):
        raise ValueError("token_and_cost freeze requires cost limits")


def load_frozen_run_config(path: str | Path) -> FrozenFiveRunConfig:
    """Load the frozen config without accepting a synthetic source."""

    candidate = Path(path)
    try:
        raw = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BatchRunnerError(
            "FROZEN_CONFIG_INVALID",
            f"Unable to load frozen config: {candidate}",
        ) from exc
    root = _as_mapping(raw, "frozen config")
    source_kind = str(root.get("source_kind") or "").strip()
    if source_kind != "production":
        raise BatchRunnerError(
            "SYNTHETIC_SOURCE_REJECTED",
            "formal five-run config requires source_kind=production",
        )
    try:
        freeze_id = str(root["freeze_id"])
        batch_schema = str(root["batch_schema"])
        checkpoint_schema = str(root["checkpoint_schema"])
        policy = _budget_policy(
            root,
            freeze_id=freeze_id,
            batch_schema=batch_schema,
            checkpoint_schema=checkpoint_schema,
        )
        budgets = _as_mapping(root["budgets"], "budgets")
        _validate_budgets(budgets, policy)
        raw_questions = root["questions"]
        if not isinstance(raw_questions, Sequence) or isinstance(
            raw_questions, (str, bytes)
        ):
            raise TypeError("questions must be an array")
        questions = tuple(
            FrozenQuestionRecord(
                question_id=str(_as_mapping(item, "questions[]")["question_id"]),
                domain=(
                    None
                    if _as_mapping(item, "questions[]").get("domain") is None
                    else str(_as_mapping(item, "questions[]")["domain"])
                ),
                question=(
                    None
                    if _as_mapping(item, "questions[]").get("question") is None
                    else str(_as_mapping(item, "questions[]")["question"])
                ),
                canonical_input_hash=(
                    None
                    if _as_mapping(item, "questions[]").get(
                        "canonical_input_hash"
                    )
                    is None
                    else str(
                        _as_mapping(item, "questions[]")[
                            "canonical_input_hash"
                        ]
                    )
                ),
                mapping_status=str(
                    _as_mapping(item, "questions[]")["mapping_status"]
                ),
            )
            for item in raw_questions
        )
        if tuple(question.question_id for question in questions) != (
            FROZEN_QUESTION_IDS
        ):
            raise ValueError(
                "questions must be the ordered frozen IDs "
                + ",".join(FROZEN_QUESTION_IDS)
            )
        provider = _as_mapping(root["provider"], "provider")
        prompt = _as_mapping(root["prompt"], "prompt")
        schema_files = tuple(
            _file_record(item, "schema_files[]")
            for item in root["schema_files"]
        )
        if len(schema_files) != 4:
            raise ValueError("exactly four schema files must be frozen")
        env_names = tuple(
            str(item)
            for item in provider["configuration_environment_variables"]
        )
        models = {
            str(name): str(model)
            for name, model in _as_mapping(provider["models"], "models").items()
        }
        return FrozenFiveRunConfig(
            freeze_id=freeze_id,
            frozen_at=str(root["frozen_at"]),
            source_kind=source_kind,
            authoritative_pdf=_file_record(
                root["authoritative_pdf"], "authoritative_pdf"
            ),
            production_question_source=_file_record(
                root["production_question_source"],
                "production_question_source",
            ),
            question_id_field=str(root["question_id_field"]),
            questions=questions,
            provider_name=str(provider["name"]),
            route_id=str(provider["route_id"]),
            models=models,
            model_version=str(provider["model_version"]),
            provider_environment_variables=env_names,
            prompt_version=str(prompt["version"]),
            prompt_file=_file_record(prompt, "prompt"),
            batch_schema=batch_schema,
            checkpoint_schema=checkpoint_schema,
            schema_files=schema_files,
            approved_t01_commit=str(root["approved_t01_commit"]),
            t01_public_interface=str(root["t01_public_interface"]),
            t03_public_interfaces=tuple(
                str(item) for item in root["t03_public_interfaces"]
            ),
            budget_policy=policy,
            budgets=budgets,
            price_snapshot=(
                None
                if root.get("price_snapshot") is None
                else _as_mapping(root["price_snapshot"], "price_snapshot")
            ),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise BatchRunnerError(
            "FROZEN_CONFIG_INVALID",
            "frozen config is missing a required WB5 field",
        ) from exc


def _owned_path(repo_root: Path, frozen_path: str) -> Path:
    pure = PurePosixPath(frozen_path.replace("\\", "/"))
    if (
        PurePosixPath(frozen_path).is_absolute()
        or PureWindowsPath(frozen_path).is_absolute()
        or ".." in pure.parts
        or not pure.parts
    ):
        raise BatchRunnerError(
            "FROZEN_PATH_INVALID",
            f"Frozen path is not repository-relative: {frozen_path}",
        )
    root = repo_root.resolve(strict=False)
    candidate = root.joinpath(*pure.parts).resolve(strict=False)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise BatchRunnerError(
            "FROZEN_PATH_INVALID",
            f"Frozen path escapes repository root: {frozen_path}",
        ) from exc
    return candidate


def _hash_file(path: Path, hash_mode: str) -> str:
    if hash_mode == RAW_BYTES_SHA256:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    if hash_mode == UTF8_LF_NORMALIZED_TEXT_SHA256:
        text = path.read_bytes().decode("utf-8-sig")
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    raise ValueError(f"unsupported frozen file hash mode: {hash_mode}")


def _verify_file(
    record: FrozenFileRecord,
    repo_root: Path,
    *,
    prefix: str,
) -> tuple[PreflightIssue, ...]:
    try:
        candidate = _owned_path(repo_root, record.path)
    except BatchRunnerError as exc:
        return (PreflightIssue(exc.error_code, str(exc)),)
    if candidate.is_symlink() or not candidate.is_file():
        return (
            PreflightIssue(
                f"{prefix}_MISSING",
                f"Frozen file is missing or not regular: {record.path}",
            ),
        )
    issues: list[PreflightIssue] = []
    actual_size = candidate.stat().st_size
    if record.size is not None and actual_size != record.size:
        issues.append(
            PreflightIssue(
                f"{prefix}_SIZE_MISMATCH",
                f"Frozen size mismatch for {record.path}",
            )
        )
    try:
        actual_hash = _hash_file(candidate, record.hash_mode)
    except UnicodeError:
        issues.append(
            PreflightIssue(
                f"{prefix}_TEXT_ENCODING_INVALID",
                f"Frozen text file is not valid UTF-8: {record.path}",
            )
        )
        return tuple(issues)
    if actual_hash != record.sha256:
        issues.append(
            PreflightIssue(
                f"{prefix}_SHA256_MISMATCH",
                f"Frozen SHA-256 mismatch for {record.path}",
            )
        )
    return tuple(issues)


def verify_authoritative_sources(
    config: FrozenFiveRunConfig,
    repo_root: str | Path,
) -> SourceProvenanceResult:
    root = Path(repo_root)
    issues = list(
        _verify_file(config.authoritative_pdf, root, prefix="SOURCE")
    )
    issues.extend(
        _verify_file(
            config.production_question_source,
            root,
            prefix="SOURCE",
        )
    )
    return SourceProvenanceResult(tuple(issues))


def compute_canonical_question_input_hash(record: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        dict(record),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def load_and_map_authoritative_questions(
    config: FrozenFiveRunConfig,
    repo_root: str | Path,
) -> dict[str, dict[str, Any]]:
    """Load exactly 125 records and map only by record["id"]."""

    provenance = verify_authoritative_sources(config, repo_root)
    if not provenance.passed:
        first = provenance.issues[0]
        raise BatchRunnerError(first.code, first.message)
    if config.question_id_field != "id":
        raise BatchRunnerError(
            "QUESTION_ID_MAPPING_INVALID",
            'formal mapping must be question_id = record["id"]',
        )
    source_path = _owned_path(Path(repo_root), config.production_question_source.path)
    try:
        raw = json.loads(source_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BatchRunnerError(
            "QUESTION_SOURCE_INVALID",
            "production question source is not valid UTF-8 JSON",
        ) from exc
    records: Any = raw.get("questions") if isinstance(raw, Mapping) else raw
    if not isinstance(records, list) or len(records) != EXPECTED_QUESTION_COUNT:
        raise BatchRunnerError(
            "QUESTION_COUNT_MISMATCH",
            (
                "production question source must contain "
                f"{EXPECTED_QUESTION_COUNT} records"
            ),
        )
    by_id: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            raise BatchRunnerError(
                "QUESTION_RECORD_INVALID",
                f"question record {index} is not an object",
            )
        question_id = record.get("id")
        if not isinstance(question_id, str) or not question_id.strip():
            raise BatchRunnerError(
                "QUESTION_ID_MAPPING_INVALID",
                f"question record {index} has no non-empty id",
            )
        if question_id in by_id:
            raise BatchRunnerError(
                "QUESTION_ID_DUPLICATE",
                f"duplicate question id: {question_id}",
            )
        by_id[question_id] = dict(record)
    missing = [
        question_id
        for question_id in FROZEN_QUESTION_IDS
        if question_id not in by_id
    ]
    if missing:
        raise BatchRunnerError(
            "FROZEN_QUESTION_MISSING",
            f"frozen question IDs are missing: {missing}",
        )
    return {question_id: by_id[question_id] for question_id in FROZEN_QUESTION_IDS}


def verify_frozen_question_text(
    config: FrozenFiveRunConfig,
    mapped: Mapping[str, Mapping[str, Any]],
) -> tuple[PreflightIssue, ...]:
    issues: list[PreflightIssue] = []
    for frozen in config.questions:
        if (
            frozen.mapping_status != "verified"
            or not (frozen.domain or "").strip()
            or not (frozen.question or "").strip()
            or frozen.canonical_input_hash is None
        ):
            issues.append(
                PreflightIssue(
                    "FROZEN_QUESTION_NOT_EVALUATED",
                    f"{frozen.question_id} has no verified authoritative mapping",
                )
            )
            continue
        actual = mapped.get(frozen.question_id)
        if actual is None:
            issues.append(
                PreflightIssue(
                    "FROZEN_QUESTION_MISSING",
                    f"{frozen.question_id} is absent from the mapped source",
                )
            )
            continue
        if (
            actual.get("id") != frozen.question_id
            or actual.get("domain") != frozen.domain
            or actual.get("question") != frozen.question
            or compute_canonical_question_input_hash(actual)
            != frozen.canonical_input_hash
        ):
            issues.append(
                PreflightIssue(
                    "FROZEN_QUESTION_MISMATCH",
                    f"{frozen.question_id} text, domain, ID, or canonical hash changed",
                )
            )
    return tuple(issues)


def verify_frozen_code_files(
    config: FrozenFiveRunConfig,
    repo_root: str | Path,
) -> tuple[PreflightIssue, ...]:
    root = Path(repo_root)
    issues = list(_verify_file(config.prompt_file, root, prefix="CODE_FILE"))
    for record in config.schema_files:
        issues.extend(_verify_file(record, root, prefix="CODE_FILE"))
    return tuple(issues)


def verify_provider_configuration_boolean(
    variable_names: Sequence[str],
    *,
    environment: Mapping[str, str] | None = None,
) -> bool:
    """Return only configured true/false; never return provider values."""

    source = os.environ if environment is None else environment
    names = tuple(name for name in variable_names if name.strip())
    return bool(names) and all(
        bool(str(source.get(name, "")).strip()) for name in names
    )


def _default_git_runner(
    command: tuple[str, ...],
    cwd: Path,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def verify_t01_gate_availability(
    approved_commit: str,
    repo_root: str | Path,
    *,
    git_runner: GitRunner = _default_git_runner,
    import_module: Callable[[str], Any] = importlib.import_module,
) -> GateAvailabilityResult:
    command = (
        "git",
        "merge-base",
        "--is-ancestor",
        approved_commit,
        "HEAD",
    )
    result = git_runner(command, Path(repo_root))
    if result.returncode != 0:
        return GateAvailabilityResult(
            False,
            "T01_GATE_VERSION_UNAVAILABLE",
            "approved T01 commit is not proven to be an ancestor of HEAD",
        )
    try:
        module = import_module("app.evidence")
        interface = getattr(module, "precheck_bundle_for_validation")
        if not callable(interface):
            raise AttributeError("interface is not callable")
    except (ImportError, AttributeError):
        return GateAvailabilityResult(
            False,
            "T01_INTERFACE_UNAVAILABLE",
            "T01 precheck_bundle_for_validation is unavailable",
        )
    return GateAvailabilityResult(
        True,
        "T01_GATE_AVAILABLE",
        "approved T01 commit and public precheck interface are available",
    )


def verify_t03_gate_availability(
    *,
    import_module: Callable[[str], Any] = importlib.import_module,
) -> GateAvailabilityResult:
    try:
        contracts = import_module("app.contracts.validation")
        workflow = import_module("app.workflow.quality_gates")
        validation_context = getattr(contracts, "ValidationContext")
        gate_result = getattr(contracts, "GateResult")
        validation_report = getattr(contracts, "ValidationReport")
        quality_gates = getattr(workflow, "run_all_quality_gates")
        required = (
            getattr(validation_context, "model_validate"),
            getattr(gate_result, "from_legacy"),
            getattr(validation_report, "from_context"),
            quality_gates,
        )
        if not all(callable(item) for item in required):
            raise AttributeError("T03 interface is not callable")
    except (ImportError, AttributeError):
        return GateAvailabilityResult(
            False,
            "T03_INTERFACE_UNAVAILABLE",
            "one or more frozen T03 public interfaces are unavailable",
        )
    return GateAvailabilityResult(
        True,
        "T03_GATE_AVAILABLE",
        "frozen T03 public interfaces are available",
    )


def _verify_clean_worktree(
    repo_root: Path,
    git_runner: GitRunner,
) -> PreflightIssue | None:
    result = git_runner(("git", "status", "--porcelain"), repo_root)
    if result.returncode != 0:
        return PreflightIssue(
            "GIT_STATUS_UNAVAILABLE",
            "unable to verify Git worktree status",
        )
    if result.stdout.strip():
        return PreflightIssue(
            "GIT_WORKTREE_DIRTY",
            "formal provider preflight requires a clean Git worktree",
        )
    return None


def run_five_run_preflight(
    config_path: str | Path,
    repo_root: str | Path,
    *,
    environment: Mapping[str, str] | None = None,
    provider_configured_override: bool | None = None,
    injected_price_snapshot: Mapping[str, Any] | None = None,
    git_runner: GitRunner = _default_git_runner,
) -> FiveRunPreflightResult:
    """Run offline checks only; this function never invokes a provider."""

    root = Path(repo_root).resolve(strict=False)
    config = load_frozen_run_config(config_path)
    issues: list[PreflightIssue] = []
    source = verify_authoritative_sources(config, root)
    issues.extend(source.issues)
    if source.passed:
        try:
            mapped = load_and_map_authoritative_questions(config, root)
        except BatchRunnerError as exc:
            issues.append(PreflightIssue(exc.error_code, str(exc)))
        else:
            issues.extend(verify_frozen_question_text(config, mapped))
    else:
        issues.extend(
            PreflightIssue(
                "FROZEN_QUESTION_NOT_EVALUATED",
                (
                    f"{record.question_id} cannot be verified without the "
                    "authoritative source"
                ),
            )
            for record in config.questions
        )
    issues.extend(verify_frozen_code_files(config, root))
    dirty = _verify_clean_worktree(root, git_runner)
    if dirty is not None:
        issues.append(dirty)
    provider_configured = (
        verify_provider_configuration_boolean(
            config.provider_environment_variables,
            environment=environment,
        )
        if provider_configured_override is None
        else provider_configured_override
    )
    if not provider_configured:
        issues.append(
            PreflightIssue(
                "PROVIDER_CONFIGURATION_MISSING",
                "provider configuration boolean is false",
            )
        )
    if (
        config.price_snapshot_required
        and config.price_snapshot is None
        and injected_price_snapshot is None
    ):
        issues.append(
            PreflightIssue(
                "PRICE_SNAPSHOT_REQUIRED",
                "a frozen operator-supplied price snapshot is required",
            )
        )
    t01 = verify_t01_gate_availability(
        config.approved_t01_commit,
        root,
        git_runner=git_runner,
    )
    if not t01.available:
        issues.append(PreflightIssue(t01.code, t01.message))
    t03 = verify_t03_gate_availability()
    if not t03.available:
        issues.append(PreflightIssue(t03.code, t03.message))
    unique: list[PreflightIssue] = []
    seen: set[tuple[str, str]] = set()
    for issue in issues:
        key = (issue.code, issue.message)
        if key not in seen:
            seen.add(key)
            unique.append(issue)
    status = (
        "FIVE_REAL_RUNS_BLOCKED"
        if unique
        else "FIVE_REAL_RUNS_READY_FOR_PROVIDER_PREFLIGHT"
    )
    return FiveRunPreflightResult(
        status=status,
        issues=tuple(unique),
        source_provenance=source,
        provider_configured=provider_configured,
        t01=t01,
        t03=t03,
        budget_policy_version=config.budget_policy_version,
        budget_mode=config.budget_mode,
        cost_accounting_required=config.cost_accounting_required,
        price_snapshot_required=config.price_snapshot_required,
        provider_preflight_executed=False,
        provider_calls=0,
    )
