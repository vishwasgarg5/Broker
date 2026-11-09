"""NSE official UDiFF cash-market bhavcopy ingestion.

Only official NSE archive URLs are used. No provider fallback is attempted.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import time
import urllib.error
import urllib.request
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from .validation import ValidationError, validate_ohlcv_record, validate_unique_sessions

NSE_SOURCE_ID = "NSE_CM_UDIFF_BHAVCOPY"
NSE_ARCHIVE_TEMPLATE = (
    "https://nsearchives.nseindia.com/content/cm/"
    "BhavCopy_NSE_CM_0_0_0_{yyyymmdd}_F_0000.csv.zip"
)
REQUIRED_COLUMNS = {
    "TradDt", "TckrSymb", "SctySrs", "OpnPric", "HghPric",
    "LwPric", "ClsPric", "TtlTradgVol",
}
USER_AGENT = "BROKER-research-pipeline/0.1 (GitHub Actions; contact: repository maintainer)"


def _download(url: str, attempts: int = 3) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/zip,application/octet-stream,*/*",
            "Accept-Encoding": "identity",
        },
    )
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                if response.status != 200:
                    raise ValidationError(f"NSE returned HTTP {response.status}")
                payload = response.read()
                if not payload:
                    raise ValidationError("NSE returned an empty archive")
                return payload
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise
            if exc.code in (403, 429, 500, 502, 503, 504) and attempt + 1 < attempts:
                time.sleep(2 ** attempt)
                continue
            raise ValidationError(f"NSE download failed with HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt + 1 < attempts:
                time.sleep(2 ** attempt)
                continue
            raise ValidationError(f"NSE download failed: {exc}") from exc
    raise ValidationError("NSE download exhausted retries")


def _extract_csv(archive: bytes) -> bytes:
    try:
        with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
            names = [n for n in zipped.namelist() if n.lower().endswith(".csv")]
            if len(names) != 1:
                raise ValidationError(f"Expected one CSV in NSE ZIP, found {len(names)}")
            return zipped.read(names[0])
    except (zipfile.BadZipFile, OSError) as exc:
        raise ValidationError("NSE bhavcopy is not a valid ZIP archive") from exc


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValidationError(f"Unexpected NSE trade date: {value!r}") from exc


def normalize_bhavcopy(csv_bytes: bytes, expected_session: date, retrieved_at: str) -> list[dict]:
    try:
        text = csv_bytes.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        headers = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - headers
        if missing:
            raise ValidationError(f"NSE UDiFF columns missing: {sorted(missing)}")
        normalized = []
        for raw in reader:
            if (raw.get("SctySrs") or "").strip().upper() != "EQ":
                continue
            symbol = (raw.get("TckrSymb") or "").strip().upper()
            if not symbol:
                raise ValidationError("NSE bhavcopy contains an empty equity symbol")
            trade_date = _parse_date(raw["TradDt"])
            if trade_date != expected_session:
                raise ValidationError(
                    f"Requested {expected_session}, but archive contains {trade_date}"
                )
            try:
                open_, high, low, close = (
                    float(raw["OpnPric"]), float(raw["HghPric"]),
                    float(raw["LwPric"]), float(raw["ClsPric"]),
                )
                volume = float(raw["TtlTradgVol"])
            except (TypeError, ValueError) as exc:
                raise ValidationError(f"Non-numeric OHLCV for {symbol}") from exc
            record = {
                "schema_version": "1.0.0",
                "date": trade_date.isoformat(),
                "symbol": symbol,
                "exchange": "NSE",
                "asset_class": "equity_cash",
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": int(volume) if volume.is_integer() else volume,
                "source": NSE_SOURCE_ID,
                "retrieved_at": retrieved_at,
            }
            validate_ohlcv_record(record)
            normalized.append(record)
    except UnicodeDecodeError as exc:
        raise ValidationError("NSE CSV is not UTF-8/UTF-8-SIG text") from exc

    if not normalized:
        raise ValidationError("NSE bhavcopy contained no EQ records")
    validate_unique_sessions(normalized)
    return normalized


def latest_available_session(target_date: date, lookback_days: int = 10) -> tuple[date, bytes]:
    """Find latest published NSE bhavcopy <= target_date; only 404 advances date."""
    for offset in range(lookback_days + 1):
        session = target_date - timedelta(days=offset)
        url = NSE_ARCHIVE_TEMPLATE.format(yyyymmdd=session.strftime("%Y%m%d"))
        try:
            return session, _download(url)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                continue
            raise
    raise ValidationError(
        f"No NSE UDiFF bhavcopy found in {lookback_days + 1} calendar days ending {target_date}"
    )


def write_ingestion(session: date, archive: bytes, records: list[dict], root: Path) -> dict:
    raw_dir = root / "data" / "raw" / "nse" / "cm"
    normalized_dir = root / "data" / "normalized" / "ohlcv"
    manifest_dir = root / "data" / "manifests"
    for directory in (raw_dir, normalized_dir, manifest_dir):
        directory.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(timezone.utc).isoformat()
    raw_hash = hashlib.sha256(archive).hexdigest()
    revision = raw_hash[:12]
    raw_path = raw_dir / f"bhavcopy_{session:%Y%m%d}_{revision}.zip"
    raw_path.write_bytes(archive)

    normalized_path = normalized_dir / f"nse_equity_{session.isoformat()}_{revision}.csv"
    fieldnames = list(records[0])
    with normalized_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    manifest = {
        "schema_version": "1.0.0",
        "dataset": "ohlcv",
        "source_id": NSE_SOURCE_ID,
        "source_url": NSE_ARCHIVE_TEMPLATE.format(yyyymmdd=session.strftime("%Y%m%d")),
        "exchange": "NSE",
        "session_date": session.isoformat(),
        "retrieved_at": stamp,
        "raw_sha256": raw_hash,
        "normalized_sha256": hashlib.sha256(normalized_path.read_bytes()).hexdigest(),
        "raw_file": str(raw_path.relative_to(root)),
        "normalized_file": str(normalized_path.relative_to(root)),
        "record_count": len(records),
        "series_filter": "EQ",
        "research_only": True,
    }
    manifest_path = manifest_dir / f"nse_cm_{session.isoformat()}_{revision}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def run(target_date: date | None = None, root: Path | None = None) -> dict:
    root = root or Path.cwd()
    target_date = target_date or datetime.now(timezone.utc).date()
    session, archive = latest_available_session(target_date)
    csv_bytes = _extract_csv(archive)
    retrieved_at = datetime.now(timezone.utc).isoformat()
    records = normalize_bhavcopy(csv_bytes, session, retrieved_at)
    manifest = write_ingestion(session, archive, records, root)
    print(json.dumps({
        "status": "PASS",
        "session_date": session.isoformat(),
        "records": len(records),
        "source_id": NSE_SOURCE_ID,
        "manifest": f"data/manifests/nse_cm_{session.isoformat()}_{manifest['raw_sha256'][:12]}.json",
    }, indent=2))
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", help="Latest acceptable exchange session (YYYY-MM-DD)")
    args = parser.parse_args()
    requested = date.fromisoformat(args.date) if args.date else None
    run(requested)


if __name__ == "__main__":
    main()
