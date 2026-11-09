# Phase 2 — NSE ingestion adapter (initial slice)

## Implemented
- Official NSE CM UDiFF daily bhavcopy downloader using the documented archive naming convention.
- ZIP integrity checks and strict UDiFF required-column checks.
- EQ-series normalization to the repository OHLCV contract.
- Session-date equality checks, positive finite OHLC checks, non-negative finite volume, duplicate-session rejection.
- Immutable raw ZIP, normalized CSV, and per-ingestion JSON manifest with SHA-256 hashes, source ID, URL, session date, and retrieval timestamp.
- Official NSE Indices Nifty 50 constituent CSV snapshot with raw and normalized copies, observation timestamp, and hashes.
- Pre-market workflow now runs the ingestion pipeline and uploads a run-scoped artifact; any source, schema, or quality failure fails the job.

## Source selection
- NSE CM UDiFF archive: `https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_YYYYMMDD_F_0000.csv.zip`
- Nifty 50 current constituent list: `https://nsearchives.nseindia.com/content/indices/ind_nifty50list.csv`
- Official holiday reference: `https://www.nseindia.com/resources/exchange-communication-holidays`

The NSE UDiFF archive is the primary daily OHLCV input. No Yahoo Finance or third-party fallback is used. A 404 while checking a candidate date advances to the prior calendar date; 403, 429, server errors after retries, malformed archives, and invalid content fail the workflow. The downloaded file's embedded trade date must equal the requested candidate date.

## Critical limitations — do not promote downstream
1. The current Nifty 50 constituent file is a point-in-time *observation*, not an effective-dated membership history. Each snapshot is retained as a separate artifact with `pit_eligible=false`. Historical constituent membership, additions/removals, and delisted names must be reconstructed from effective-dated NSE Indices notices before survivorship-safe model training.
2. The current slice covers NSE cash EQ daily bars only. BSE cash, Bank Nifty constituents/index OHLC, sector indices, ETFs, F&O contracts, and intraday bars are not yet enabled.
3. Official exchange holiday and special-session calendar ingestion/reconciliation is not yet implemented. Do not infer a trading session from weekdays alone.
4. Corporate-action ingestion and adjusted/total-return price series are not yet implemented. Raw bhavcopy prices remain unadjusted.
5. Historical backfill, gap reconciliation, late/corrected bhavcopy versioning review, and repeated scheduled-run validation remain open.
6. Data is uploaded as a run-scoped Actions artifact and is not committed to Git. Artifact retention is 30 days; durable long-term archive strategy remains to be decided before research history is considered complete.

## Run locally
```bash
PYTHONPATH=src python -m unittest discover -s tests -v
python src/data_pipeline.py
python src/data_pipeline.py --date 2026-11-06
```

The date option is the latest acceptable exchange session; without it, the adapter searches backward up to ten calendar days for the latest published official NSE bhavcopy. This is a retrieval rule, not a substitute for the official market calendar.
