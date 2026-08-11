"""
T06 Wave B：时序 CSV 适配（schema / 时间索引 / 缺失 / 重复 / 受控单位转换）。

清洗动作写入可追溯 cleaning_log；禁止不可追溯删除或静默填补。
"""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.contracts.multimodal import (
    ColumnUnitBinding,
    MultimodalArtifact,
    Provenance,
    TableData,
)
from app.multimodal.errors import ExtractionError

_CONFIDENCE_PASS = 0.80
_CONFIDENCE_REVIEW = 0.50

# 仅允许显式声明的受控单位转换。
_UNIT_FACTORS: dict[tuple[str, str], float] = {
    ("s", "ms"): 1000.0,
    ("ms", "s"): 0.001,
    ("mV", "V"): 0.001,
    ("V", "mV"): 1000.0,
}


@dataclass
class CleaningRecord:
    """单条可追溯清洗记录。"""

    action: str
    detail: str
    row_index: int | None = None


@dataclass
class TimeseriesExtractionResult:
    artifact: MultimodalArtifact
    cleaning_log: list[CleaningRecord] = field(default_factory=list)


def _load_sidecar(csv_path: Path) -> dict[str, Any]:
    sidecar = csv_path.with_suffix(csv_path.suffix + ".schema.json")
    if not sidecar.is_file():
        # 允许同 stem 的 .schema.json
        alt = csv_path.with_name(csv_path.stem + ".schema.json")
        if alt.is_file():
            sidecar = alt
        else:
            raise ExtractionError(
                f"timeseries schema sidecar missing for {csv_path.name}"
            )
    try:
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ExtractionError(f"invalid schema sidecar: {exc}") from exc
    if not isinstance(payload, dict):
        raise ExtractionError("schema sidecar must be an object")
    return payload


def extract_timeseries_artifact(source_path: str) -> TimeseriesExtractionResult:
    path = Path(source_path)
    if not path.is_file():
        raise ExtractionError(f"timeseries source not found: {source_path}")
    schema = _load_sidecar(path)

    time_field = schema.get("time_field")
    value_fields = schema.get("value_fields")
    units = schema.get("units") or {}
    convert_to = schema.get("convert_to") or {}
    page = int(schema.get("page", 1))
    confidence = float(schema.get("confidence", 0.9))
    source_type = schema.get("source_type", "csv")
    if not time_field or not isinstance(value_fields, list) or not value_fields:
        raise ExtractionError("schema requires time_field and value_fields")
    if confidence < 0.0 or confidence > 1.0:
        raise ExtractionError("confidence must be in [0, 1]")

    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ExtractionError("CSV has no header")
        fieldnames = list(reader.fieldnames)
        required_cols = [time_field, *value_fields]
        for col in required_cols:
            if col not in fieldnames:
                raise ExtractionError(f"schema/unit conflict: missing column {col!r}")

        log: list[CleaningRecord] = []
        raw_rows: list[dict[str, str]] = []
        for idx, row in enumerate(reader):
            raw_rows.append({k: (row.get(k) or "") for k in required_cols})

    # 重复时间点：标记异常，不静默丢弃。
    seen: dict[str, int] = {}
    anomaly_flags: list[str] = []
    for idx, row in enumerate(raw_rows):
        t = row[time_field].strip()
        if t == "":
            raise ExtractionError(
                f"missing time at row {idx}: refuse silent fill"
            )
        if t in seen:
            anomaly_flags.append(f"duplicate_time:{t}")
            log.append(
                CleaningRecord(
                    action="flag_duplicate_time",
                    detail=f"time={t} first_row={seen[t]}",
                    row_index=idx,
                )
            )
        else:
            seen[t] = idx
        for vf in value_fields:
            if row[vf].strip() == "":
                anomaly_flags.append(f"missing_value:{vf}@{t}")
                log.append(
                    CleaningRecord(
                        action="flag_missing_value",
                        detail=f"field={vf} time={t}",
                        row_index=idx,
                    )
                )

    # 时间顺序检查（字符串/数值）；乱序失败。
    times = [r[time_field].strip() for r in raw_rows]
    try:
        numeric_times = [float(t) for t in times]
        if numeric_times != sorted(numeric_times):
            raise ExtractionError("time index not sorted ascending")
    except ValueError as exc:
        raise ExtractionError(f"non-numeric time field: {exc}") from exc

    # 受控单位转换。
    out_units: dict[str, str] = {}
    for col in value_fields:
        src_unit = str(units.get(col) or "").strip()
        if not src_unit:
            raise ExtractionError(f"unit missing for column {col!r}")
        dst_unit = str(convert_to.get(col) or src_unit).strip()
        if dst_unit != src_unit:
            key = (src_unit, dst_unit)
            if key not in _UNIT_FACTORS:
                raise ExtractionError(
                    f"unsupported unit conversion {src_unit}->{dst_unit}"
                )
            factor = _UNIT_FACTORS[key]
            for idx, row in enumerate(raw_rows):
                raw = row[col].strip()
                if raw == "":
                    continue
                try:
                    row[col] = str(float(raw) * factor)
                except ValueError as exc:
                    raise ExtractionError(
                        f"non-numeric value in {col} row {idx}"
                    ) from exc
            log.append(
                CleaningRecord(
                    action="unit_convert",
                    detail=f"{col}:{src_unit}->{dst_unit} factor={factor}",
                )
            )
        out_units[col] = dst_unit
    out_units[time_field] = str(units.get(time_field) or "s")

    headers = [time_field, *value_fields, "anomaly_flags"]
    rows: list[list[str]] = []
    for idx, row in enumerate(raw_rows):
        flags = [f for f in anomaly_flags if f.endswith(f"@{row[time_field].strip()}") or f"duplicate_time:{row[time_field].strip()}" == f]
        # also attach duplicates matching this time
        flag_cell = ";".join(
            f
            for f in anomaly_flags
            if row[time_field].strip() in f
        )
        rows.append(
            [
                row[time_field].strip(),
                *[row[vf].strip() for vf in value_fields],
                flag_cell,
            ]
        )

    if confidence < _CONFIDENCE_REVIEW or anomaly_flags:
        # 有异常标记时不得标 passed
        status = "needs_review" if confidence >= _CONFIDENCE_REVIEW else "failed"
        if confidence >= _CONFIDENCE_PASS and not anomaly_flags:
            status = "passed"
    else:
        status = "passed" if confidence >= _CONFIDENCE_PASS else "needs_review"
    if anomaly_flags and confidence >= _CONFIDENCE_PASS:
        status = "needs_review"

    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    artifact_id = str(schema.get("artifact_id") or f"ts-{digest}")
    column_units = [
        ColumnUnitBinding(column=k, unit=v) for k, v in out_units.items()
    ]
    # anomaly_flags 列无单位
    artifact = MultimodalArtifact(
        artifact_id=artifact_id,
        modality="timeseries",
        provenance=Provenance(
            source_path=str(path),
            source_type=source_type,  # type: ignore[arg-type]
            page=page,
            bbox=None,
        ),
        units=[u for u in out_units.values()],
        column_units=column_units,
        axes=None,
        legend=list(value_fields),
        data=TableData(headers=headers, rows=rows),
        confidence=confidence,
        validation_status=status,  # type: ignore[arg-type]
    )
    # 将 cleaning log 摘要写入 legend 之外的可追溯旁路：附加到 units 注释不可行；
    # 调用方通过 TimeseriesExtractionResult.cleaning_log 获取。
    _ = log
    return TimeseriesExtractionResult(artifact=artifact, cleaning_log=log)
