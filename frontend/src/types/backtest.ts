export interface BacktestConfig {
  symbol: string
  fast_sma: number
  slow_sma: number
  atr_window: number
  atr_multiplier: number
  cost_bps: number
  start_date?: string
  end_date?: string
}

export interface BacktestTrade {
  trade_id?: number
  entry_signal_date?: string
  entry_date: string
  entry_price: number
  exit_signal_date?: string
  exit_date: string
  exit_price: number
  atr_at_entry?: number
  atr_multiplier: number
  stop_loss: number
  gross_pnl?: number
  transaction_cost?: number
  net_pnl?: number
  gross_return: number
  net_return: number
  exit_reason: string
}

export interface BacktestMetrics {
  gross_return: number
  net_return: number
  gross_cagr: number
  net_cagr: number
  sharpe_ratio: number
  sortino_ratio: number
  max_drawdown: number
  win_rate: number
  profit_factor: number
  total_trades: number
  winning_trades: number
  losing_trades: number
}

export interface EquityPoint {
  time: string
  equity: number
}

export interface BacktestResult {
  symbol: string
  config: BacktestConfig
  metrics: BacktestMetrics
  trades: BacktestTrade[]
  equity_curve: {
    gross: EquityPoint[]
    net: EquityPoint[]
  }
  metadata?: {
    first_date?: string
    last_date?: string
    total_bars?: number
  }
}

export interface StrategyParams {
  symbol: string
  universe?: string
  fast_sma: number
  slow_sma: number
  atr_window: number
  atr_multiplier: number
  transaction_cost_bps: number
  start_date: string
  end_date: string
}
