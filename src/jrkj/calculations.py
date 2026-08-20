"""Deterministic financial calculations used by JRKJ agents."""

from __future__ import annotations

from typing import Any, Dict, List


def period_kind(period: int) -> str:
    suffix = str(period)[4:]
    if suffix == "1231":
        return "annual"
    if suffix == "0630":
        return "half_year"
    if suffix in {"0331", "0930"}:
        return "quarter_cumulative"
    return "other"


def calculate_change(start_value: float, end_value: float, label: str) -> Dict[str, Any]:
    difference = end_value - start_value
    percent = None if start_value == 0 else difference / abs(start_value) * 100
    return {
        "label": label,
        "start_value": start_value,
        "end_value": end_value,
        "difference": round(difference, 6),
        "percent_change": None if percent is None else round(percent, 6),
        "formula": "(end_value - start_value) / abs(start_value) * 100",
    }


def classify_series(periods: List[int], values: List[float], label: str) -> Dict[str, Any]:
    if len(periods) != len(values) or len(values) < 2:
        raise ValueError("periods and values must have the same length of at least two")
    pairs = sorted(zip((int(period) for period in periods), values))
    sorted_periods = [period for period, _ in pairs]
    sorted_values = [value for _, value in pairs]
    changes = [right - left for left, right in zip(sorted_values, sorted_values[1:])]
    if all(change > 0 for change in changes):
        trend = "increasing"
    elif all(change < 0 for change in changes):
        trend = "decreasing"
    elif all(change == 0 for change in changes):
        trend = "flat"
    else:
        trend = "fluctuating"
    kinds = [period_kind(period) for period in sorted_periods]
    comparable = len(set(kinds)) == 1
    warning = "" if comparable else "Mixed cumulative reporting periods are not directly comparable."
    return {
        "label": label,
        "periods": sorted_periods,
        "values": sorted_values,
        "period_kinds": kinds,
        "comparable": comparable,
        "trend": trend if comparable else "not_comparable",
        "raw_sequence_shape": trend,
        "changes": changes,
        "warning": warning,
    }
