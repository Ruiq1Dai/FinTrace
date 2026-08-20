"""Deterministic, explainable Level-2 financial scorecards.

Scores are screening indicators only; they are never fraud or solvency findings.
"""
from __future__ import annotations

from typing import Any, Iterable
from .risk_thresholds import POLICY_VERSION, get_threshold


def _value(rows: dict[int, dict[str, Any]], period: int, field: str) -> float | None:
    value = rows.get(period, {}).get(field)
    return None if value is None else float(value)


def beneish_m_score(ds: dict[str, float | None]) -> dict[str, Any]:
    """Calculate the eight-factor Beneish M score from precomputed indexes."""
    required = ("DSRI", "GMI", "AQI", "SGI", "DEPI", "SGAI", "LVGI", "TATA")
    missing = [key for key in required if ds.get(key) is None]
    if missing:
        return {"score": None, "missing": missing, "formula": "-4.84 + 0.92DSRI + 0.528GMI + 0.404AQI + 0.892SGI + 0.115DEPI - 0.172SGAI + 4.679TATA - 0.327LVGI"}
    score = (-4.84 + .92 * ds["DSRI"] + .528 * ds["GMI"] + .404 * ds["AQI"] +
             .892 * ds["SGI"] + .115 * ds["DEPI"] - .172 * ds["SGAI"] +
             4.679 * ds["TATA"] - .327 * ds["LVGI"])
    threshold = get_threshold("beneish_m_score")
    return {"score": round(score, 6), "threshold": threshold, "screening_flag": score > threshold,
            "policy_version": POLICY_VERSION,
            "formula": "Beneish M-score; threshold is a screening convention, not a conclusion"}


def altman_z_score(values: dict[str, float | None], private: bool = False) -> dict[str, Any]:
    """Calculate Altman Z (public) or Z' (private) using supplied ratios."""
    keys = ("A", "B", "C", "D", "E")
    missing = [key for key in keys if values.get(key) is None]
    if missing:
        return {"score": None, "missing": missing}
    coeff = (0.717, 0.847, 3.107, 0.420, 0.998) if private else (1.2, 1.4, 3.3, 0.6, 1.0)
    score = sum(a * float(values[k]) for a, k in zip(coeff, keys))
    distress, grey = get_threshold("altman_distress"), get_threshold("altman_grey")
    return {"score": round(score, 6), "zone": "distress" if score < distress else ("grey" if score < grey else "safe"),
            "model": "Z-prime" if private else "Z", "policy_version": POLICY_VERSION,
            "scope_warning": "Original public Z model is scope-sensitive; do not apply blindly to financial or non-manufacturing firms.",
            "formula": "weighted sum of A-E ratios"}


def piotroski_f_score(metrics: dict[str, bool | None]) -> dict[str, Any]:
    """Sum the nine binary Piotroski signals."""
    names = ("roa_positive", "cfo_positive", "roa_improving", "accrual_quality",
             "leverage_improving", "liquidity_improving", "no_dilution", "margin_improving", "turnover_improving")
    missing = [name for name in names if metrics.get(name) is None]
    score = sum(bool(metrics[name]) for name in names if metrics.get(name) is not None)
    return {"score": score, "max_score": 9, "missing": missing,
            "quality_band": "weak" if score <= 3 else ("neutral" if score <= 6 else "strong"),
            "policy_version": POLICY_VERSION,
            "formula": "sum of nine binary accounting signals"}


def peer_zscore(value: float, peers: Iterable[float]) -> dict[str, Any]:
    values = [float(item) for item in peers]
    if len(values) < 2:
        return {"z_score": None, "warning": "at least two peers are required"}
    mean = sum(values) / len(values)
    variance = sum((item - mean) ** 2 for item in values) / (len(values) - 1)
    std = variance ** 0.5
    z_score = None if std == 0 else round((float(value) - mean) / std, 6)
    min_peers = int(get_threshold("minimum_peer_count"))
    return {"z_score": z_score, "peer_count": len(values), "mean": mean, "std": std,
            "minimum_peer_count": min_peers,
            "screening_flag": bool(z_score is not None and len(values) >= min_peers and abs(z_score) >= get_threshold("peer_z_score")),
            "policy_version": POLICY_VERSION,
            "warning": "Use only with same-industry, same-period, same-scope peers."}
