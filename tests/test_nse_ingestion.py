import csv
import io
import sys
import unittest
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from broker.nse_ingest import normalize_bhavcopy, _extract_csv
from broker.data_pipeline import fetch_nifty50_symbols
from broker.validation import ValidationError

HEADERS = "TradDt,TckrSymb,SctySrs,OpnPric,HghPric,LwPric,ClsPric,TtlTradgVol"
def csv_bytes(rows):
    return (HEADERS + "\n" + "\n".join(rows) + "\n").encode()

class NSEIngestionTests(unittest.TestCase):
    def test_normalizes_eq_and_ignores_non_eq(self):
        payload = csv_bytes([
            "2026-11-06,RELIANCE,EQ,100,105,99,103,1000",
            "2026-11-06,RELIANCE,BE,100,105,99,103,20",
        ])
        records = normalize_bhavcopy(payload, date(2026, 11, 6), "2026-11-06T12:00:00+00:00")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["symbol"], "RELIANCE")
        self.assertEqual(records[0]["volume"], 1000)
        self.assertEqual(records[0]["source"], "NSE_CM_UDIFF_BHAVCOPY")

    def test_rejects_wrong_session_date(self):
        with self.assertRaises(ValidationError):
            normalize_bhavcopy(csv_bytes(["2026-11-05,RELIANCE,EQ,100,105,99,103,1000"]),
                               date(2026, 11, 6), "2026-11-06T12:00:00+00:00")

    def test_rejects_missing_required_column(self):
        with self.assertRaises(ValidationError):
            normalize_bhavcopy(b"TradDt,TckrSymb\n2026-11-06,RELIANCE",
                               date(2026, 11, 6), "2026-11-06T12:00:00+00:00")

    def test_rejects_invalid_ohlc(self):
        with self.assertRaises(ValidationError):
            normalize_bhavcopy(csv_bytes(["2026-11-06,RELIANCE,EQ,100,98,99,103,1000"]),
                               date(2026, 11, 6), "2026-11-06T12:00:00+00:00")

    def test_extracts_single_csv_from_zip(self):
        memory = io.BytesIO()
        with zipfile.ZipFile(memory, "w") as zipped:
            zipped.writestr("bhavcopy.csv", csv_bytes(["2026-11-06,RELIANCE,EQ,100,105,99,103,1000"]))
        self.assertTrue(_extract_csv(memory.getvalue()).startswith(b"TradDt"))

    def test_rejects_zip_without_csv(self):
        memory = io.BytesIO()
        with zipfile.ZipFile(memory, "w") as zipped:
            zipped.writestr("readme.txt", "no csv")
        with self.assertRaises(ValidationError): _extract_csv(memory.getvalue())

    def test_rejects_duplicate_symbol_rows(self):
        with self.assertRaises(ValidationError):
            normalize_bhavcopy(csv_bytes([
                "2026-11-06,RELIANCE,EQ,100,105,99,103,1000",
                "2026-11-06,RELIANCE,EQ,100,105,99,103,1000",
            ]), date(2026, 11, 6), "2026-11-06T12:00:00+00:00")

if __name__ == "__main__":
    unittest.main()
