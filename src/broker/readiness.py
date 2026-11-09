"""Promotion/readiness gates that fail closed."""
from __future__ import annotations
from datetime import date, datetime
from typing import Mapping
from .validation import ValidationError

REQUIRED_RESEARCH_GATES = (
    "data_quality_passed",
    "point_in_time_passed",
    "chronological_validation_passed",
    "benchmark_comparison_passed",
    "costs_and_slippage_included",
    "risk_limits_passed",
    "paper_trading_reconciled",
)

def require_gates(gates: Mapping[str, bool]) -> None:
    missing = [name for name in REQUIRED_RESEARCH_GATES if name not in gates]
    failed = [name for name in REQUIRED_RESEARCH_GATES if gates.get(name) is not True]
    if missing or failed:
        raise ValidationError(f"Readiness blocked; missing={missing}, failed={failed}")

def validate_next_session(decision_at: str, target_session: str) -> None:
    try:
        decision = datetime.fromisoformat(decision_at.replace("Z", "+00:00"))
        target = date.fromisoformat(target_session)
    except ValueError as exc:
        raise ValidationError("Invalid decision timestamp or target session") from exc
    if decision.tzinfo is None:
        raise ValidationError("decision_at must be timezone-aware")
    if target <= decision.date():
        raise ValidationError("Target session must be later than the decision date")
