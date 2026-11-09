# BROKER

India-first, research-only quantitative market research and paper-trading platform. BROKER does not place live orders, connect to brokers, or handle real-money execution.

## Phase 1 status

Repository foundation is being established. Phase 1 is complete only after configuration contracts, schemas, validation helpers, workflow scaffolding, documentation, and automated tests are present and pass.

## Scope

- Initial priority: NSE/BSE cash equities, index/sector benchmarks, F&O reference data, and liquid ETFs.
- Secondary coverage: mutual funds, IPO events, G-Secs/SGBs, and selected MCX commodities.
- Deferred: US equities, crypto, and international ETFs.
- Operating mode: research forecasts and paper trading only.

## Safety principles

- No broker credentials, live order endpoints, or real-money execution paths.
- Point-in-time data and chronological evaluation; no look-ahead or survivorship leakage.
- Missing, stale, malformed, or unreconciled data fails closed.
- Predictions remain research-only until paper-trading and out-of-sample gates pass.
- Every data artifact records its source, retrieval time, exchange session date, and schema version.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/READINESS_GATES.md](docs/READINESS_GATES.md), and [docs/DATA_DICTIONARY.md](docs/DATA_DICTIONARY.md).
