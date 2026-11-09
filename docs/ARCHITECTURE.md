# BROKER architecture — Phase 1

## Mission and boundaries
BROKER is an India-first market research and paper-trading system. Outputs are forecasts, factor research, risk estimates, and simulated paper records. It must not connect to brokers or place live orders.

## Four-script pipeline
1. data_pipeline.py: ingest exchange calendars, point-in-time universes, OHLCV, fundamentals source records, and corporate actions.
2. fundamental_engine.py: validate and adjust corporate actions; compute point-in-time value, quality, growth, and momentum factors.
3. ml_predictor.py: build causal features, train chronological models, run walk-forward evaluation and backtests, then emit research-only forecasts.
4. evaluator.py: reconcile predictions with actual sessions, compare benchmarks, calculate costs-aware paper results, and append auditable metrics.

Shared contracts and validation live under schemas/ and src/broker/. Configuration under config/ is the single source of truth; scripts must not duplicate universe or risk constants.

## Initial market scope
- Priority 1: NSE/BSE cash equities, Nifty 50, Bank Nifty, sectoral indices.
- Priority 2: F&O reference data and liquid ETFs.
- Priority 3: mutual funds, IPO events, G-Secs/SGBs, and selected MCX commodities.
- Deferred: US equities, crypto, international ETFs.

## Artifact boundaries
- data/: raw and normalized market data; large generated files are not committed by default.
- predictions/: research-only forecasts with model and data provenance.
- logs/: append-only evaluation and run metadata.
- models/: versioned model metadata/artifacts, subject to retention and reproducibility policy.
- GitHub Actions artifacts are run-scoped and named with workflow/run IDs. Cross-run consumption must verify source workflow, commit, run conclusion, artifact identity, schema version, and target session.

## Execution model
Pre-market and post-market are separate workflows. Each validates configuration and contracts. Pre-market currently publishes only a foundation manifest; post-market does not claim to evaluate forecasts until verified predictions and actuals exist. Scheduled UTC times are approximate and must be gated by the official exchange calendar.

## Design rules
- Use explicit source IDs, retrieval timestamps, session dates, and raw-response hashes.
- Keep raw data immutable; corrections create new versions with lineage.
- Preserve point-in-time universe membership, including delisted constituents.
- Features must be available at or before the decision timestamp.
- Fit scalers, imputers, selectors, and hyperparameters on training windows only.
- Split by time, not random rows; prevent overlapping-label leakage.
- Compare with simple baselines and include fees, taxes, slippage, and liquidity constraints.
- A failed gate blocks promotion; it never silently downgrades to a pass.
