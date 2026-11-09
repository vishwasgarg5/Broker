import csv
import io
import sys
import unittest
import zipfile
from datetime import date
from pathlib import Path
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from broker.nse_ingest import normalize_bhavcopy, _extract_csv
from broker.data_pipeline import fetch_nifty50_symbols, main as run_data_pipeline
from broker.validation import ValidationError

HEADERS = "TradDt,TckrSymb,SctySrs,OpnPric,HghPric,LwPric,ClsPric,TtlTradgVol"
def csv_bytes(rows):
    return (HEADERS + "\n" + "\n".join(rows) + "\n").encode()

def nifty50_bytes():
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["Company Name", "Industry", "Symbol", "Series", "ISIN Code"])
    writer.writeheader()
    for index in range(50):
        writer.writerow({
            "Company Name": f"Company {index}",
            "Industry": "Test",
            "Symbol": f"TEST{index:02d}",
            "Series": "EQ",
            "ISIN Code": f"INE{index:07d}",
        })
    return output.getvalue().encode()


class NSEIngestionTests(unittest.TestCase):
    def test_nifty50_retries_transient_timeout_then_succeeds(self):
        class Response:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self): return nifty50_bytes()

        with patch("broker.data_pipeline.urllib.request.urlopen",
                   side_effect=[TimeoutError("temporary timeout"), Response()]) as urlopen, \
             patch("broker.data_pipeline.time.sleep") as sleep:
            rows, raw = fetch_nifty50_symbols(attempts=3, timeout=60)
        self.assertEqual(len(rows), 50)
        self.assertEqual(raw, nifty50_bytes())
        self.assertEqual(urlopen.call_count, 2)
        self.assertEqual(urlopen.call_args_list[0].kwargs["timeout"], 60)
        sleep.assert_called_once_with(1)

    def test_nifty50_persistent_timeout_fails_closed_after_retries(self):
        with patch("broker.data_pipeline.urllib.request.urlopen",
                   side_effect=TimeoutError("persistent timeout")) as urlopen, \
             patch("broker.data_pipeline.time.sleep") as sleep:
            with self.assertRaisesRegex(ValidationError, "persistent timeout"):
                fetch_nifty50_symbols(attempts=3, timeout=60)
        self.assertEqual(urlopen.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    def test_pipeline_preserves_udiff_result_when_nifty50_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            udiff_manifest = {"source_id": "NSE_CM_UDIFF_BHAVCOPY", "record_count": 1}
            with patch("sys.argv", ["data_pipeline.py"]), \
                 patch("broker.data_pipeline.Path.cwd", return_value=root), \
                 patch("broker.data_pipeline.ingest_nse_ohlcv", return_value=udiff_manifest) as udiff, \
                 patch("broker.data_pipeline.fetch_nifty50_symbols",
                       side_effect=ValidationError("Nifty endpoint timeout")), \
                 patch("builtins.print") as output:
                with self.assertRaises(SystemExit) as raised:
                    run_data_pipeline()
            self.assertEqual(raised.exception.code, 1)
            udiff.assert_called_once_with(None, root)
            printed = output.call_args.args[0]
            self.assertIn('"status": "FAIL"', printed)
            self.assertIn('"ohlcv_ingestion"', printed)
            self.assertIn("Nifty endpoint timeout", printed)

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
