import { BacktestResult } from '../types/backtest'

interface StoredResult {
  result: BacktestResult
  params: any
}

export default function Results() {
  // Get result from localStorage
  const stored = localStorage.getItem('lastBacktestResult')
  const data: StoredResult | null = stored ? JSON.parse(stored) : null
  const result = data?.result || null

  if (!result) {
    return (
      <div className="max-w-4xl mx-auto">
        <h1 className="text-2xl font-semibold text-slate-100 mb-4">Backtest Results</h1>
        <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6 text-center">
          <p className="text-slate-400">No backtest results found. Please run a backtest first.</p>
          <button
            onClick={() => window.location.href = '/strategy-lab'}
            className="mt-4 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md"
          >
            Go to Strategy Lab
          </button>
        </div>
      </div>
    )
  }

  const { metrics, trades, equity_curve } = result

  // Calculate drawdown from equity curve
  const drawdownData = equity_curve.net.map((point, i) => {
    const maxPeak = Math.max(...equity_curve.net.slice(0, i + 1).map(p => p.equity))
    return ((point.equity - maxPeak) / maxPeak) * 100
  })

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-semibold text-slate-100">Backtest Results</h1>
        <div className="flex gap-2">
          <button
            onClick={() => window.location.href = '/strategy-lab'}
            className="bg-slate-800 hover:bg-slate-700 text-slate-200 px-4 py-2 rounded-md text-sm"
          >
            ← Modify Strategy
          </button>
        </div>
      </div>

      {/* Strategy Summary */}
      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <span className="text-slate-400">Asset:</span>
            <span className="text-slate-100 ml-2 font-mono">{result.symbol}</span>
          </div>
          <div>
            <span className="text-slate-400">Strategy:</span>
            <span className="text-slate-100 ml-2">SMA {result.config.fast_sma} / SMA {result.config.slow_sma}</span>
          </div>
          <div>
            <span className="text-slate-400">ATR:</span>
            <span className="text-slate-100 ml-2">{result.config.atr_window} × {result.config.atr_multiplier}</span>
          </div>
          <div>
            <span className="text-slate-400">Cost:</span>
            <span className="text-slate-100 ml-2">{result.config.cost_bps} bps</span>
          </div>
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
          <div className="text-slate-400 text-xs">Net Return</div>
          <div className={`text-2xl font-bold mt-1 ${metrics.net_return >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
            {metrics.net_return.toFixed(2)}%
          </div>
        </div>
        <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
          <div className="text-slate-400 text-xs">Gross Return</div>
          <div className="text-2xl font-bold mt-1 text-slate-100">
            {metrics.gross_return.toFixed(2)}%
          </div>
        </div>
        <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
          <div className="text-slate-400 text-xs">CAGR</div>
          <div className={`text-2xl font-bold mt-1 ${metrics.net_cagr >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
            {metrics.net_cagr.toFixed(2)}%
          </div>
        </div>
        <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
          <div className="text-slate-400 text-xs">Sharpe Ratio</div>
          <div className="text-2xl font-bold mt-1 text-slate-100">
            {metrics.sharpe_ratio.toFixed(2)}
          </div>
        </div>
        <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
          <div className="text-slate-400 text-xs">Max Drawdown</div>
          <div className="text-2xl font-bold mt-1 text-rose-400">
            {metrics.max_drawdown.toFixed(2)}%
          </div>
        </div>
        <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
          <div className="text-slate-400 text-xs">Win Rate</div>
          <div className="text-2xl font-bold mt-1 text-slate-100">
            {metrics.win_rate.toFixed(1)}%
          </div>
        </div>
        <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
          <div className="text-slate-400 text-xs">Trade Count</div>
          <div className="text-2xl font-bold mt-1 text-slate-100">
            {metrics.total_trades}
          </div>
        </div>
        <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
          <div className="text-slate-400 text-xs">Profit Factor</div>
          <div className="text-2xl font-bold mt-1 text-slate-100">
            {metrics.profit_factor.toFixed(2)}
          </div>
        </div>
      </div>

      {/* Equity Curve */}
      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
        <h3 className="text-slate-200 font-medium mb-4">Equity Curve</h3>
        <div className="h-64 flex items-end space-x-1">
          {equity_curve.net.slice(-100).map((point, idx) => {
            const maxEq = Math.max(...equity_curve.net.slice(-100).map(p => p.equity))
            const height = (point.equity / maxEq) * 100
            return (
              <div
                key={idx}
                className="flex-1 bg-blue-500 hover:bg-blue-400 transition-colors"
                style={{ height: `${height}%` }}
                title={`${point.time}: ${point.equity.toFixed(2)}`}
              />
            )
          })}
        </div>
        <div className="flex justify-between text-xs text-slate-500 mt-2">
          <span>{equity_curve.net[equity_curve.net.length - 100]?.time || 'Start'}</span>
          <span>{equity_curve.net[equity_curve.net.length - 1]?.time || 'End'}</span>
        </div>
      </div>

      {/* Drawdown */}
      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
        <h3 className="text-slate-200 font-medium mb-4">Drawdown</h3>
        <div className="h-32 flex items-end space-x-1">
          {drawdownData.slice(-100).map((dd, idx) => (
            <div
              key={idx}
              className="flex-1 bg-rose-500 hover:bg-rose-400 transition-colors"
              style={{ height: `${Math.abs(dd)}%` }}
              title={`${equity_curve.net[equity_curve.net.length - 100 + idx]?.time || ''}: ${dd.toFixed(2)}%`}
            />
          ))}
        </div>
        <div className="text-xs text-slate-500 mt-2">
          Max Drawdown: <span className="text-rose-400">{metrics.max_drawdown.toFixed(2)}%</span>
        </div>
      </div>

      {/* Trade Log */}
      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
        <h3 className="text-slate-200 font-medium mb-4">Trade Log ({trades.length} trades)</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-slate-400 border-b border-slate-800">
                <th className="text-left pb-2">#</th>
                <th className="text-left pb-2">Entry Date</th>
                <th className="text-right pb-2">Entry Price</th>
                <th className="text-left pb-2">Exit Date</th>
                <th className="text-right pb-2">Exit Price</th>
                <th className="text-right pb-2">Stop Loss</th>
                <th className="text-right pb-2">Gross Ret</th>
                <th className="text-right pb-2">Net Ret</th>
                <th className="text-left pb-2">Exit Reason</th>
              </tr>
            </thead>
            <tbody>
              {trades.map((trade, idx) => (
                <tr key={idx} className="border-b border-slate-800/50 hover:bg-slate-800/30">
                  <td className="py-2 text-slate-500">{idx + 1}</td>
                  <td className="py-2 text-slate-300 font-mono text-xs">{trade.entry_date}</td>
                  <td className="py-2 text-right text-slate-300">₹{trade.entry_price.toFixed(2)}</td>
                  <td className="py-2 text-slate-300 font-mono text-xs">{trade.exit_date}</td>
                  <td className="py-2 text-right text-slate-300">₹{trade.exit_price.toFixed(2)}</td>
                  <td className="py-2 text-right text-slate-400">₹{trade.stop_loss.toFixed(2)}</td>
                  <td className={`py-2 text-right ${trade.gross_return >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                    {trade.gross_return.toFixed(2)}%
                  </td>
                  <td className={`py-2 text-right font-medium ${trade.net_return >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                    {trade.net_return.toFixed(2)}%
                  </td>
                  <td className="py-2 text-slate-400 text-xs">{trade.exit_reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {trades.length === 0 && (
            <div className="text-center py-8 text-slate-500">
              No qualifying trades were generated for this configuration.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
