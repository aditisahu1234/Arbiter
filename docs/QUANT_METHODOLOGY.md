# Arbiter Quant Methodology

## ATR (Average True Range)

**Default**: Wilder's Smoothing (RMA) with n=14

```
ATR_t = ((n-1) * ATR_{t-1} + TR_t) / n
```

Initialized with n-period simple mean of TR.

**Configurable**: SMA or EMA smoothing available.

## Signal Generation

**SMA Crossover Strategy**:
- BUY when SMA_fast crosses above SMA_slow (fast_t > slow_t AND fast_{t-1} <= slow_{t-1})
- SELL when SMA_fast crosses below SMA_slow (fast_t < slow_t AND fast_{t-1} >= slow_{t-1})

## Execution Rules

**Default**: Next-bar-open execution
- Signal generated at close of bar t (using data available through t)
- Execution at open of bar t+1 (O_{t+1})
- Prevents look-ahead bias

**Stop-loss**:
- Calculated as: entry_price - atr_multiplier * ATR
- Intraday check on bar t+1: if L_{t+1} <= stop_loss, exit triggered
- Exit price: min(O_{t+1}, stop_loss) - handles gap-down

## Transaction Cost Model

Multi-tier model parameterized by basis points (bps) of trade turnover:

| Component | Default (bps) | Notes |
|-----------|--------------|-------|
| Brokerage | 5.0 | Max 0.05% per SEBI |
| Exchange Tx | 0.325 | NSE rate |
| STT (sell) | 10.0 | Equity delivery |
| Stamp Duty | 1.5 | Buy + sell |
| Slippage | 5.0 | Configurable |
| GST | 18% on brokerage+exchange | Indirect |

**Default round-trip**: 10 bps (0.10%) total slippage/costs

## Market Benchmark

- **Market Proxy**: NIFTY 50 (^NSEI)
- **Risk-Free Rate**: 91-day G-India T-bill yield, annualized to daily:
  ```
  Rf_daily = (1 + Rf_annual)^(1/252) - 1
  ```
  Default fallback: 6.50% annualized

## CAPM

```
Ri - Rf = α + β(Rm - Rf) + ε
```

Outputs: alpha, beta, R², standard error, t-stat, p-value, observations

## Fama-French 3-Factor

```
Ri - Rf = α + β_m(Rm - Rf) + β_s*SMB + β_h*HML + ε
```

**Factor Data**: India-specific factors from IIM Ahmedabad / Agarwalla, Jacob, Varma
or computed synthetically across NIFTY 500 universe ranked by market cap and book-to-market.

**Outputs**: Market beta, Size beta, Value beta, Alpha, R², ANOVA statistics

## Price Series

- Both Raw OHLCV and Dividend/Split Adjusted prices stored
- Indicators and signals use **Adjusted Close** to prevent false signals across splits/dividends
