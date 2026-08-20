"""Versioned screening conventions, centralized for review and evaluation.

These values classify investigation leads only. They must never be rendered as
an audit, legal, fraud, or solvency determination.
"""
from __future__ import annotations

POLICY_VERSION = "risk-policy-v1"

DEFAULT_THRESHOLDS = {
    "beneish_m_score": -1.78,
    "altman_distress": 1.81,
    "altman_grey": 2.99,
    "signal_growth_excess_pct": 10.0,
    "peer_z_score": 2.0,
    "minimum_peer_count": 10,
    "minimum_comparable_periods_for_high": 2,
    "minimum_external_evidence_for_high": 1,
}

THRESHOLD_METADATA = {
    "beneish_m_score": {
        "meaning": "M-score above threshold is a manipulation-screening flag",
        "limitation": "Not a fraud determination; validate scope and input indexes.",
    },
    "altman_distress": {
        "meaning": "Z-score below threshold is a financial-distress screening flag",
        "limitation": "Original public-company model is scope-sensitive and not a fraud test.",
    },
    "altman_grey": {
        "meaning": "Z-score below threshold is in the grey screening zone",
        "limitation": "Do not apply without a compatible industry and statement scope.",
    },
    "signal_growth_excess_pct": {
        "meaning": "Receivables or inventory growth exceeds revenue growth by this margin",
        "limitation": "Project convention requiring business-context review.",
    },
    "peer_z_score": {
        "meaning": "Absolute peer z-score at or above threshold is an outlier flag",
        "limitation": "Requires a same-period, same-industry peer set.",
    },
}


def get_threshold(name: str, overrides: dict[str, float] | None = None) -> float:
    values = dict(DEFAULT_THRESHOLDS)
    values.update(overrides or {})
    if name not in values:
        raise KeyError("unknown risk threshold: " + name)
    return float(values[name])


def policy_metadata() -> dict[str, object]:
    """Return a JSON-compatible copy for evidence and audit artifacts."""
    return {
        "policy_version": POLICY_VERSION,
        "thresholds": dict(DEFAULT_THRESHOLDS),
        "metadata": {key: dict(value) for key, value in THRESHOLD_METADATA.items()},
        "warning": "Screening conventions are not legal, audit, fraud, or solvency findings.",
    }
