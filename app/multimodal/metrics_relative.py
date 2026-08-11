"""图表数值相对误差（canonical：非零 gold 相对误差 ≤5%；零值用显式绝对容限）。"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


DEFAULT_ZERO_ABS_TOL = 1e-6


@dataclass
class PointError:
    series: str
    index: int
    predicted: float | None
    gold: float | None
    relative_error: float | None
    absolute_error: float | None
    pass_threshold: bool
    needs_human_review: bool
    reason: str


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(v) or math.isinf(v):
        return None
    return v


def relative_or_absolute_error(
    predicted: Any,
    gold: Any,
    *,
    relative_threshold: float = 0.05,
    zero_abs_tol: float = DEFAULT_ZERO_ABS_TOL,
) -> PointError:
    """
    Canonical chart metric:
      non-zero gold: abs(pred-gold)/abs(gold) <= 0.05
      zero gold: abs(pred-gold) <= zero_abs_tol (explicit)
    """
    p = _to_float(predicted)
    g = _to_float(gold)
    if g is None:
        return PointError(
            series="",
            index=-1,
            predicted=p,
            gold=None,
            relative_error=None,
            absolute_error=None,
            pass_threshold=False,
            needs_human_review=True,
            reason="gold_missing_or_non_finite",
        )
    if p is None:
        return PointError(
            series="",
            index=-1,
            predicted=None,
            gold=g,
            relative_error=None,
            absolute_error=None,
            pass_threshold=False,
            needs_human_review=True,
            reason="predicted_missing_or_non_finite",
        )
    abs_err = abs(p - g)
    if abs(g) == 0.0:
        ok = abs_err <= zero_abs_tol
        return PointError(
            series="",
            index=-1,
            predicted=p,
            gold=g,
            relative_error=None,
            absolute_error=abs_err,
            pass_threshold=ok,
            needs_human_review=not ok,
            reason="zero_gold_absolute_tol" if ok else "zero_gold_abs_exceeded",
        )
    rel = abs_err / abs(g)
    # Tolerate binary float noise at the exact 5% boundary (e.g. 1.05/1.0).
    ok = rel <= relative_threshold + 1e-12
    return PointError(
        series="",
        index=-1,
        predicted=p,
        gold=g,
        relative_error=rel,
        absolute_error=abs_err,
        pass_threshold=ok,
        needs_human_review=not ok,
        reason="within_5pct" if ok else "relative_error_exceeds_5pct",
    )


def evaluate_chart_series(
    predicted_rows: list[list[str]],
    gold_rows: list[list[str]],
    *,
    relative_threshold: float = 0.05,
    zero_abs_tol: float = DEFAULT_ZERO_ABS_TOL,
) -> dict[str, Any]:
    """
    Rows expected as [series, x, y] for both predicted and gold.
    Align by (series, x); missing pairs fail closed into human review.
    """
    gold_map: dict[tuple[str, str], str] = {}
    for row in gold_rows:
        if len(row) < 3:
            continue
        gold_map[(row[0], row[1])] = row[2]
    pred_map: dict[tuple[str, str], str] = {}
    for row in predicted_rows:
        if len(row) < 3:
            continue
        pred_map[(row[0], row[1])] = row[2]

    keys = sorted(set(gold_map) | set(pred_map))
    points: list[PointError] = []
    for i, key in enumerate(keys):
        series, x = key
        pe = relative_or_absolute_error(
            pred_map.get(key),
            gold_map.get(key),
            relative_threshold=relative_threshold,
            zero_abs_tol=zero_abs_tol,
        )
        if key not in gold_map:
            pe = PointError(
                series=series,
                index=i,
                predicted=_to_float(pred_map.get(key)),
                gold=None,
                relative_error=None,
                absolute_error=None,
                pass_threshold=False,
                needs_human_review=True,
                reason="missing_gold_point",
            )
        elif key not in pred_map:
            pe = PointError(
                series=series,
                index=i,
                predicted=None,
                gold=_to_float(gold_map.get(key)),
                relative_error=None,
                absolute_error=None,
                pass_threshold=False,
                needs_human_review=True,
                reason="missing_predicted_point",
            )
        else:
            pe.series = series
            pe.index = i
        points.append(pe)

    n = len(points)
    n_pass = sum(1 for p in points if p.pass_threshold)
    rate = (n_pass / n) if n else 0.0
    return {
        "schema_version": "1.0",
        "metric": "chart_point_relative_error",
        "relative_threshold": relative_threshold,
        "zero_abs_tol": zero_abs_tol,
        "zero_abs_tol_declared": True,
        "point_count": n,
        "pass_count": n_pass,
        "pass_rate": rate,
        "meets_threshold": n > 0 and n_pass == n,
        "needs_human_review": any(p.needs_human_review for p in points),
        "points": [p.__dict__ for p in points],
    }
