"""Deterministic context packing for long-horizon financial questions."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from .persistent_memory import PersistentEvidenceMemory


WINDCODE_RE = re.compile(r"\b\d{6}\.(?:SH|SZ|BJ)\b", re.I)
TABLE_HINTS = {
    "financial_income": ("收入", "利润", "净利润", "营业利润", "投资收益", "公允价值"),
    "financial_balance": ("资产", "负债", "应收", "存货", "借款", "货币资金"),
    "financial_cashflow": ("现金流", "经营现金", "投资现金", "筹资现金"),
    "shareholders": ("股东", "持股", "控制", "穿透"),
    "announcements": ("公告", "处罚", "监管", "担保", "整改"),
    "research_reports": ("研报", "预测", "评级", "风险提示"),
}


class ContextBuilder:
    """Build a bounded, provenance-preserving context pack from long-term evidence."""

    def __init__(self, memory: Optional[PersistentEvidenceMemory] = None) -> None:
        self.memory = memory or PersistentEvidenceMemory()

    def build(self, question: str, token_budget: int = 4000) -> Dict[str, Any]:
        code_match = WINDCODE_RE.search(question.upper())
        company = code_match.group(0).upper() if code_match else ""
        if not company:
            return {"company": "", "facts": [], "context_text": ""}
        tables = [
            table for table, hints in TABLE_HINTS.items()
            if any(hint in question for hint in hints)
        ]
        candidates: List[Dict[str, Any]] = []
        for table in tables or list(TABLE_HINTS):
            candidates.extend(self.memory.recall(company, table, 100))
        # Stable ranking: directly hinted tables first, then newest observations.
        hinted = set(tables)
        candidates.sort(
            key=lambda item: (
                0 if item["table"] in hinted else 1,
                -int(item["period"]),
                item["table"],
                item["source"],
            )
        )
        max_chars = max(256, int(token_budget) * 4)
        facts: List[Dict[str, Any]] = []
        used_chars = 0
        for item in candidates:
            line = (
                f"[{item['table']} {item['period_field']}={item['period']}] "
                f"values={item['values']} source={item['source']}"
            )
            if used_chars + len(line) > max_chars:
                continue
            facts.append(item)
            used_chars += len(line) + 1
        context_text = "\n".join(
            f"- {item['table']} {item['period_field']}={item['period']}; "
            f"values={item['values']}; source={item['source']}"
            for item in facts
        )
        return {
            "company": company,
            "facts": facts,
            "fact_count": len(facts),
            "token_budget": token_budget,
            "context_text": context_text,
            "instruction": (
                "These are previously observed exact facts from the current dataset version. "
                "Reuse only with the nested source; query the original table when data is missing "
                "or the question asks for latest values."
            ),
        }
