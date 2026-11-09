# Readiness and promotion gates

Passing unit tests or completing a workflow is not evidence of predictive edge. All gates are fail-closed.

## Data readiness
- Required fields, types, units, timezone, and schema version validate.
- No duplicate symbol/exchange/session rows.
- OHLC consistency holds; prices and volumes are finite and non-negative as appropriate.
- Official calendar and special sessions reconcile with observed sessions.
- Corporate actions are sourced, effective-dated, and independently reconciled.
- Universe membership is point-in-time; delisted constituents are retained.
- Stale, missing, suspicious, or unreconciled records block downstream predictions.

## Research and model readiness
- Every feature has an availability timestamp no later than its decision timestamp.
- Chronological train/validation/test splits and walk-forward folds are used.
- Preprocessing and feature selection are fitted only on each training window.
- No target leakage, survivorship bias, or overlapping-label contamination.
- Compare against previous-close, buy-and-hold, and relevant index/ETF baselines.
- Report MAE/RMSE and directional accuracy; do not rely on MAPE near zero-valued targets.
- Report net-of-cost returns, turnover, exposure, volatility, Sharpe/Sortino, and maximum drawdown.
- Evaluate across multiple market regimes and sufficiently long untouched out-of-sample periods.

## Paper-trading readiness
- Simulate brokerage, exchange fees, taxes, spread, slippage, lot sizes, and liquidity.
- Enforce position, concentration, participation, daily-loss, and drawdown limits.
- Reconcile every simulated fill and cash/position ledger.
- Keep paper-trading records immutable and reproducible.

## Promotion policy
A model remains RESEARCH_ONLY unless every configured promotion requirement is met, including at least 252 out-of-sample sessions, five walk-forward folds, positive net expectancy, benchmark comparison, multiple regimes, paper trading, and 60 consecutive green evaluation sessions. These are minimum gates, not guarantees of future performance.

No Phase 1 component can enable live trading. Broker connectivity and live execution are prohibited by project scope.
