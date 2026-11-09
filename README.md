# BROKER

India-first, research-only quantitative market research and paper-trading platform. BROKER does not place live orders, connect to brokers, or handle real-money execution.

## Current implementation status

- **Phase 1 — foundation:** complete for foundation purposes; configuration, schemas, validation, CI and separate workflow scaffolding are present.
- **Phase 2 — data ingestion:** in progress. The first NSE adapter downloads official UDiFF cash-market bhavcopy data, normalizes EQ-series OHLCV, records immutable raw/normalized files and provenance manifests, and snapshots the current Nifty 50 constituent list.
- **Not yet production-ready:** BSE coverage, Bank Nifty/sector/ETF data, official holiday/special-session reconciliation, effective-dated historical universe membership, corporate actions, historical backfill, and sustained scheduled-run verification.

## Scope

- Initial priority: NSE/BSE cash equities, index/sector benchmarks, F&O reference data, and liquid ETFs.
- Secondary coverage: mutual funds, IPO events, G-Secs/SGBs, and selected MCX commodities.
- Deferred: US equities, crypto, and international ETFs.
- Operating mode: research forecasts and paper trading only.

## Safety principles

- No broker credentials, live order endpoints, or real-money execution paths.
- Point-in-time data and chronological evaluation; no look-ahead or survivorship leakage.
- Missing, stale, malformed, or unreconciled data fails closed.
- Current universe observations are not treated as historical effective-dated membership.
- Predictions remain research-only until paper-trading and out-of-sample gates pass.
- Every data artifact records its source, retrieval time, exchange session date, schema version, and content hashes.

## Run tests and first ingestion

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
python src/data_pipeline.py
```

The ingestion requires access to official NSE archive endpoints. A source or validation failure must stop the workflow; no silent secondary-provider fallback is configured.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Readiness gates](docs/READINESS_GATES.md)
- [Data dictionary](docs/DATA_DICTIONARY.md)
- [Phase 2 ingestion and limitations](docs/PHASE_2_INGESTION.md)
