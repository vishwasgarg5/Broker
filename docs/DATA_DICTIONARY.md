# Data dictionary — schema version 1.0.0

All timestamps must be ISO-8601 and timezone-aware. Session dates are exchange-local dates (India: Asia/Kolkata). Every dataset carries schema version and source lineage.

| Dataset | Required identity/time fields | Main payload | Contract |
|---|---|---|---|
| OHLCV | symbol, exchange, date | open, high, low, close, volume, optional adj_close | schemas/ohlcv.schema.json |
| Fundamentals | symbol, period_end, available_at | valuation, profitability, growth, balance-sheet metrics | schemas/fundamentals.schema.json |
| Corporate actions | symbol, ex_date, available_at | action_type, ratio, cash_amount, adjustment_factor | schemas/corporate_actions.schema.json |
| Universe membership | universe, symbol, effective_from, published_at | exchange, asset class, effective_to | schemas/universe_membership.schema.json |
| Market calendar | exchange, session_date | session type, trading flag, open/close times | schemas/market_calendar.schema.json |
| Factor scores | symbol, score_date, available_at | value, quality, growth, momentum, composite alpha | schemas/factor_scores.schema.json |
| Predictions | symbol, decision_at, target_session, model_version | prediction type, value, confidence, risk levels | schemas/predictions.schema.json |
| Evaluation | prediction_id, symbol, target_session, evaluated_at | actual value, errors, directional result, net paper P&L, benchmark | schemas/evaluation.schema.json |
| Paper ledger | trade_id, symbol, decision_at, fill_at | side, quantity, fill price, fees, slippage, simulation flag | schemas/paper_trades.schema.json |

## Additional datasets to formalize in Phase 2+
- Derivative contract master, expiry, lot size, strike, option type, and settlement fields.
- ETF holdings/NAV and mutual-fund NAV/distribution records.
- IPO issue timeline, allotment/listing events.
- Government security and SGB instrument/reference data.
- MCX contract specifications and commodity-specific units.

## Conventions
- Currency amounts default to INR unless a field explicitly declares another currency.
- Ratios and percentages must declare whether they are decimals or percentage points in dataset metadata; never infer units.
- Raw, adjusted, and total-return prices are distinct series and must never be mixed silently.
- Dividend adjustment methodology must be documented for each use case; price-only forecasts and total-return evaluation are not interchangeable.
- available_at means when information became publicly available to the strategy, not merely the accounting period end.
