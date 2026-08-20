"""Deterministic risk labels for the versioned JRKJ screening policy."""

from __future__ import annotations

from typing import Any, Iterable

from .risk_thresholds import POLICY_VERSION

RISK_LEVELS = {
    "insufficient_data": "数据不足",
    "none": "未发现重大异常线索",
    "low": "低风险线索",
    "medium": "中风险线索",
    "high": "高风险线索",
    "confirmed_fact": "已确认监管事实",
}

STRONG_EXTERNAL_EVIDENCE = {
    "audit_opinion",
    "announcement_body",
    "regulatory_decision",
    "court_decision",
    "verified_graph",
}


def classify_risk(
    signal_families: Iterable[str],
    external_evidence: Iterable[str] = (),
    data_sufficient: bool = True,
    comparable_periods: int = 0,
    official_finding: bool = False,
) -> dict[str, Any]:
    """Classify an investigation lead without calling it fraud.

    ``signal_families`` should contain independent categories such as
    ``revenue_cashflow``, ``receivables``, ``inventory``, ``scorecard``, or
    ``related_party``. Official findings are kept separate from model risk.
    """
    families = sorted({str(item) for item in signal_families if str(item).strip()})
    evidence = sorted({str(item) for item in external_evidence if str(item).strip()})
    strong_evidence = sorted(set(evidence) & STRONG_EXTERNAL_EVIDENCE)
    if official_finding:
        code = "confirmed_fact"
        rationale = "存在正式监管、司法或交易所文书认定；这不是模型推断。"
    elif not data_sufficient:
        code = "insufficient_data"
        rationale = "关键字段、报表口径、报告正文或实体身份不足。"
    elif not families:
        code = "none"
        rationale = "当前可比数据未触发已配置的异常类别。"
    elif len(families) >= 2 and comparable_periods >= 2 and strong_evidence:
        code = "high"
        rationale = "至少两个独立异常类别持续两个可比期间，并有强外部证据交叉支持。"
    elif len(families) >= 2 or (families and evidence):
        code = "medium"
        rationale = "存在多个异常类别，或存在一个异常类别与外部线索的交叉支持。"
    else:
        code = "low"
        rationale = "存在一个可复算的异常类别，但缺少独立外部佐证。"
    return {
        "policy_version": POLICY_VERSION,
        "risk_code": code,
        "risk_level": RISK_LEVELS[code],
        "signal_families": families,
        "external_evidence": evidence,
        "strong_external_evidence": strong_evidence,
        "comparable_periods": int(comparable_periods),
        "official_finding": bool(official_finding),
        "rationale": rationale,
        "limitation": "风险线索不等于财务造假；已确认监管事实必须引用原始文书。",
    }
