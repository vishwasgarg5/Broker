"""Phase 2 data-pipeline entry point: NSE cash OHLCV + current universe observation."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

from .nse_ingest import NSE_SOURCE_ID, USER_AGENT, run as ingest_nse_ohlcv
from .validation import ValidationError

NIFTY50_CSV_URL = "https://nsearchives.nseindia.com/content/indices/ind_nifty50list.csv"


def fetch_nifty50_symbols() -> tuple[list[dict], bytes]:
    request = urllib.request.Request(
        NIFTY50_CSV_URL,
        headers={"User-Agent": USER_AGENT, "Accept": "text/csv,*/*"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read()
    except Exception as exc:
        raise ValidationError(f"Official NSE Nifty 50 constituent download failed: {exc}") from exc
    try:
        reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig")))
        if not reader.fieldnames or "Symbol" not in reader.fieldnames:
            raise ValidationError("NSE Nifty 50 CSV does not contain required Symbol column")
        rows = []
        seen = set()
        for row in reader:
            symbol = (row.get("Symbol") or "").strip().upper()
            if not symbol:
                raise ValidationError("Nifty 50 constituent CSV contains an empty symbol")
            if symbol in seen:
                raise ValidationError(f"Duplicate Nifty 50 constituent: {symbol}")
            seen.add(symbol)
            rows.append({
                "symbol": symbol,
                "company_name": (row.get("Company Name") or "").strip(),
                "industry": (row.get("Industry") or "").strip(),
                "series": (row.get("Series") or "").strip(),
                "isin": (row.get("ISIN Code") or "").strip(),
            })
    except UnicodeDecodeError as exc:
        raise ValidationError("NSE Nifty 50 CSV is not valid UTF-8") from exc
    if len(rows) != 50:
        raise ValidationError(f"Expected 50 Nifty 50 constituents, received {len(rows)}")
    return rows, payload


def write_universe_observation(rows: list[dict], raw: bytes, root: Path) -> dict:
    observed_at = datetime.now(timezone.utc).isoformat()
    observed_date = datetime.now(timezone.utc).date().isoformat()
    directory = root / "data" / "universe" / "observations"
    manifest_dir = root / "data" / "manifests"
    directory.mkdir(parents=True, exist_ok=True)
    manifest_dir.mkdir(parents=True, exist_ok=True)
    csv_path = directory / f"nifty50_{observed_date}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    manifest = {
        "schema_version": "1.0.0",
        "dataset": "universe_observation",
        "universe": "NIFTY50",
        "exchange": "NSE",
        "source_id": "NSE_INDICES_NIFTY50_CONSTITUENTS",
        "source_url": NIFTY50_CSV_URL,
        "observed_at": observed_at,
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "normalized_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
        "record_count": len(rows),
        "pit_eligible": False,
        "pit_reason": "Current constituent list is an observation, not an effective-dated membership history.",
        "normalized_file": str(csv_path.relative_to(root)),
    }
    path = manifest_dir / f"nifty50_observation_{observed_date}.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", help="Latest acceptable NSE session (YYYY-MM-DD)")
    args = parser.parse_args()
    root = Path.cwd()
    symbols, raw = fetch_nifty50_symbols()
    universe_manifest = write_universe_observation(symbols, raw, root)
    ohlcv_manifest = ingest_nse_ohlcv(date.fromisoformat(args.date) if args.date else None, root)
    result = {
        "status": "PASS",
        "universe_observation": universe_manifest,
        "ohlcv_ingestion": ohlcv_manifest,
        "next_gate": "NIFTY50 membership remains non-PIT until effective-dated historical membership is sourced.",
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
