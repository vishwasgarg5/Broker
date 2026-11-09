"""Fail-closed validation primitives; standard-library only."""
from __future__ import annotations
import json
import math
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"

class ValidationError(ValueError):
    """Raised when data cannot safely enter the research pipeline."""

def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"Cannot load valid JSON from {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValidationError(f"Expected a JSON object in {path}")
    return value

def validate_configuration() -> None:
    for name in ("assets.json", "features.json", "risk.json", "data_sources.json"):
        if load_json(CONFIG_DIR / name).get("schema_version") != "1.0.0":
            raise ValidationError(f"{name}: unsupported schema_version")
    risk = load_json(CONFIG_DIR / "risk.json")
    if risk.get("live_execution_enabled") is not False:
        raise ValidationError("Live execution must remain explicitly disabled")
    if risk.get("broker_connectivity_enabled") is not False:
        raise ValidationError("Broker connectivity must remain explicitly disabled")
    if risk.get("mode") != "research_and_paper_only":
        raise ValidationError("BROKER must remain research/paper-only")

def validate_ohlcv_record(row: Mapping[str, Any]) -> None:
    required = {"schema_version","date","symbol","exchange","asset_class","open","high","low","close","volume","source","retrieved_at"}
    missing = required.difference(row)
    if missing:
        raise ValidationError(f"OHLCV missing required fields: {sorted(missing)}")
    if row["schema_version"] != "1.0.0":
        raise ValidationError("Unsupported OHLCV schema version")
    try:
        date.fromisoformat(str(row["date"]))
        retrieved = datetime.fromisoformat(str(row["retrieved_at"]).replace("Z","+00:00"))
    except ValueError as exc:
        raise ValidationError("Invalid OHLCV date or retrieval timestamp") from exc
    if retrieved.tzinfo is None:
        raise ValidationError("retrieved_at must include a timezone")
    if not str(row["symbol"]).strip() or not str(row["source"]).strip():
        raise ValidationError("symbol and source must be non-empty")
    prices = [row[k] for k in ("open","high","low","close")]
    if any(not isinstance(v,(int,float)) or isinstance(v,bool) or not math.isfinite(v) or v <= 0 for v in prices):
        raise ValidationError("OHLC prices must be positive finite numbers")
    if row["high"] < max(prices) or row["low"] > min(prices):
        raise ValidationError("OHLC high/low range is inconsistent")
    volume = row["volume"]
    if not isinstance(volume,(int,float)) or isinstance(volume,bool) or not math.isfinite(volume) or volume < 0:
        raise ValidationError("volume must be a non-negative finite number")

def validate_unique_sessions(rows: Iterable[Mapping[str, Any]]) -> None:
    seen: set[tuple[str,str,str]] = set()
    previous: dict[str,date] = {}
    for row in rows:
        symbol, exchange = str(row.get("symbol","")), str(row.get("exchange",""))
        try:
            session = date.fromisoformat(str(row["date"]))
        except (KeyError,ValueError) as exc:
            raise ValidationError("Every row must have an ISO session date") from exc
        key = (symbol,exchange,session.isoformat())
        if key in seen:
            raise ValidationError(f"Duplicate symbol/exchange/session: {key}")
        seen.add(key)
        if symbol in previous and session < previous[symbol]:
            raise ValidationError(f"Non-chronological rows for {symbol}")
        previous[symbol] = session

def validate_point_in_time(feature_available_at: str, decision_at: str) -> None:
    try:
        available = datetime.fromisoformat(feature_available_at.replace("Z","+00:00"))
        decision = datetime.fromisoformat(decision_at.replace("Z","+00:00"))
    except ValueError as exc:
        raise ValidationError("Point-in-time timestamps must be ISO-8601") from exc
    if available.tzinfo is None or decision.tzinfo is None:
        raise ValidationError("Point-in-time timestamps must be timezone-aware")
    if available > decision:
        raise ValidationError("Look-ahead detected: feature unavailable at decision time")

def self_check() -> None:
    validate_configuration()
    sample = {"schema_version":"1.0.0","date":"2026-11-06","symbol":"RELIANCE","exchange":"NSE","asset_class":"equity_cash","open":100.0,"high":105.0,"low":99.0,"close":103.0,"volume":1000,"source":"unit-test","retrieved_at":"2026-11-06T12:00:00+05:30"}
    validate_ohlcv_record(sample)
    validate_unique_sessions([sample])
    validate_point_in_time("2026-11-06T09:00:00+05:30","2026-11-06T09:15:00+05:30")

if __name__ == "__main__":
    self_check()
    print("BROKER Phase 1 validation self-check: PASS")
