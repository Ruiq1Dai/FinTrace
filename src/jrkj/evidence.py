"""Structured evidence shared by JRKJ agents and audit steps."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class Evidence:
    table: str
    company: str
    period_field: str
    period: int
    values: Dict[str, Any]
    source: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
