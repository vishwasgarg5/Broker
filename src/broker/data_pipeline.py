"""Phase 2 data-pipeline entry point: NSE cash OHLCV + current universe observation."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

from .nse_ingest import NSE_SOURCE_ID, USER_AGENT, run as ingest_nse_ohlcv
from .validation import ValidationError

NIFTY50_CSV_URL = "https://nsearchives.nseindia.com/content/indices/ind_nifty50list.csv"


def fetch_nifty50_symbols(attempts: int = 3, timeout: int = 60) -> tuple[list[dict], bytes]:
    """Download official Nifty 50 constituent list with retries for transient errors."""
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    request = urllib.request.Request(
        NIFTY50_CSV_URL,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/csv,*/*",
            "Accept-Encoding": "identity",
        },
    )
    last_error: Exception | None = None
    payload: bytes | None = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                if response.status != 200:
                    raise ValidationError(f"NSE Nifty 50 returned HTTP {response.status}")
                payload = response.read()
                if not payload:
                    raise ValidationError("NSE Nifty 50 returned an empty response")
            break
        except urllib.error.HTTPError as exc:
            last_error = exc
            print(f"NSE Nifty 50 request failed: URL={NIFTY50_CSV_URL} "
                  f"attempt={attempt + 1}/{attempts} HTTP={exc.code}: {exc}")
            if exc.code == 404:
                raise ValidationError("NSE Nifty 50 constituent file not found (404)") from exc
            if exc.code in (403, 429, 500, 502, 503, 504) and attempt + 1 < attempts:
                delay = 2 ** attempt
                print(f"Retrying NSE Nifty 50 request in {delay}s")
                time.sleep(delay)
                continue
            raise ValidationError(
                f"Official NSE Nifty 50 download failed with HTTP {exc.code}"
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            print(f"NSE Nifty 50 request failed: URL={NIFTY50_CSV_URL} "
                  f"attempt={attempt + 1}/{attempts}: {type(exc).__name__}: {exc}")
            if attempt + 1 < attempts:
                delay = 2 ** attempt
                print(f"Retrying NSE Nifty 50 request in {delay}s")
                time.sleep(delay)
                continue
            raise ValidationError(
                f"Official NSE Nifty 50 constituent download failed after "
                f"{attempts} attempts: {exc}"
            ) from exc
    else:
        raise ValidationError(
            f"Official NSE Nifty 50 constituent download failed after {attempts} "
            f"attempts: {last_error}"
        )

    assert payload is not None
    try:
        reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig")))
        if not reader.fieldnames or "Symbol" not in reader.fieldnames:
            raise ValidationError("NSE Nifty 50 CSV does not contain required Symbol column")
        rows = []
        seen: set[str] = set()
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
    observed_now = datetime.now(timezone.utc)
    observed_date = observed_now.date().isoformat()
    observation_id = observed_now.strftime("%Y%m%dT%H%M%SZ")
    directory = root / "data" / "universe" / "observations"
    raw_dir = root / "data" / "raw" / "nse" / "indices"
    manifest_dir = root / "data" / "manifests"
    directory.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    manifest_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"nifty50_{observation_id}.csv"
    raw_path.write_bytes(raw)
    csv_path = directory / f"nifty50_{observation_id}.csv"
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
    manifest["raw_file"] = str(raw_path.relative_to(root))
    path = manifest_dir / f"nifty50_observation_{observation_id}.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", help="Latest acceptable NSE session (YYYY-MM-DD)")
    args = parser.parse_args()
    root = Path.cwd()
    target_date = date.fromisoformat(args.date) if args.date else None
    result = {"status": "PASS", "failures": []}

    # Run the primary cash-market feed first. A failure here does not prevent
    # the independent Nifty 50 observation from being attempted.
    try:
        result["ohlcv_ingestion"] = ingest_nse_ohlcv(target_date, root)
    except Exception as exc:
        result["status"] = "FAIL"
        result["failures"].append({
            "source": NSE_SOURCE_ID,
            "error": f"{type(exc).__name__}: {exc}",
        })

    try:
        symbols, raw = fetch_nifty50_symbols()
        result["universe_observation"] = write_universe_observation(symbols, raw, root)
    except Exception as exc:
        result["status"] = "FAIL"
        result["failures"].append({
            "source": "NSE_INDICES_NIFTY50_CONSTITUENTS",
            "error": f"{type(exc).__name__}: {exc}",
        })

    result["next_gate"] = (
        "NIFTY50 membership remains non-PIT until effective-dated historical membership is sourced."
    )
    print(json.dumps(result, indent=2))
    if result["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
