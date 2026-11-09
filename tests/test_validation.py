import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from broker.validation import ValidationError, self_check, validate_ohlcv_record, validate_point_in_time, validate_unique_sessions
from broker.readiness import REQUIRED_RESEARCH_GATES, require_gates, validate_next_session

def row(day="2026-11-06", symbol="RELIANCE"):
    return {"schema_version":"1.0.0","date":day,"symbol":symbol,"exchange":"NSE","asset_class":"equity_cash","open":100.0,"high":105.0,"low":99.0,"close":103.0,"volume":1000,"source":"test","retrieved_at":"2026-11-06T12:00:00+05:30"}

class ValidationTests(unittest.TestCase):
    def test_configuration_and_self_check(self): self_check()
    def test_rejects_invalid_ohlc_range(self):
        item=row(); item["high"]=98.0
        with self.assertRaises(ValidationError): validate_ohlcv_record(item)
    def test_rejects_missing_source(self):
        item=row(); item["source"]=""
        with self.assertRaises(ValidationError): validate_ohlcv_record(item)
    def test_rejects_duplicate_sessions(self):
        with self.assertRaises(ValidationError): validate_unique_sessions([row(),row()])
    def test_rejects_non_chronological_rows(self):
        with self.assertRaises(ValidationError): validate_unique_sessions([row("2026-11-06"),row("2026-11-05")])
    def test_rejects_lookahead(self):
        with self.assertRaises(ValidationError): validate_point_in_time("2026-11-06T10:00:00+05:30","2026-11-06T09:15:00+05:30")
    def test_accepts_point_in_time_feature(self):
        validate_point_in_time("2026-11-06T09:00:00+05:30","2026-11-06T09:15:00+05:30")
    def test_readiness_fails_closed_when_gate_missing(self):
        with self.assertRaises(ValidationError): require_gates({})
    def test_readiness_passes_only_when_all_gates_true(self):
        require_gates({name: True for name in REQUIRED_RESEARCH_GATES})
    def test_target_must_be_future_session(self):
        with self.assertRaises(ValidationError): validate_next_session("2026-11-06T10:00:00+05:30","2026-11-06")
    def test_accepts_future_target_session(self):
        validate_next_session("2026-11-06T16:00:00+05:30","2026-11-09")

if __name__ == "__main__": unittest.main()
