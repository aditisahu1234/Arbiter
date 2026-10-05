import { useEffect, useState } from 'react'
import { fetchAssetOhlcv, fetchSMA, fetchATR, runBacktest, runCAPM, runFF3 } from '../services/api'
import { OhlcBar } from '../types'

interface Position {
  id: number
  symbol: string
  status: string
  signal_date: string
  entry_date: string
  entry_price: number
  stop_price: number
  current_price: number
  gross_pnl: number
  net_pnl: number
  created_at: string
  last_updated: string
}

interface Trade {
  entry_date: string
  entry_price: number
  exit_date: string
  exit_price: number
  stop_price: number
  exit_reason: string
  gross_pnl: number
  cost: number
  net_pnl: number
}

interface StrategyCalc {
  date: string
  open: number
  high: number
  low: number
  close: number
  adjusted_close: number
  fast_sma: number
  slow_sma: number
  prev_fast_sma: number
  prev_slow_sma: number
  true_range: number
  atr: number
  signal: string
  stop_price: number
  entry_date: string
  entry_price: number
  exit_date: string
  exit_price: number
  exit_reason: string
  position: string
}

interface StrategyResult {
  symbol: string
  config: {
    fast_sma: number
    slow_sma: number
    atr_window: number
    atr_multiplier: number
    cost_bps: number
  }
  calculations: StrategyCalc[]
  signals: Trade[]
  trades: Trade[]
}

interface MarketStatus {
  is_open: boolean
  current_time_ist: string
  next_event: string
}

export default function AssetDetail({ symbol }: { symbol: string }) {
  const [ohlcv, setOhlcv] = useState<OhlcBar[]>([])
  const [sma, setSma] = useState<any>(null)
  const [atr, setAtr] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  
  // Strategy state
  const [fastSma, setFastSma] = useState(10)
  const [slowSma, setSlowSma] = useState(50)
  const [atrWindow, setAtrWindow] = useState(14)
  const [atrMultiplier, setAtrMultiplier] = useState(2.0)
  const [costBps, setCostBps] = useState(10)
  const [startDate, setStartDate] = useState('2021-10-01')
  const [endDate, setEndDate] = useState('2026-10-01')
  const [running, setRunning] = useState(false)
  const [strategyResult, setStrategyResult] = useState<StrategyResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  
  // Position state
  const [positions, setPositions] = useState<any[]>([])
  const [trades, setTrades] = useState<any[]>([])
  const [marketStatus, setMarketStatus] = useState<MarketStatus | null>(null)
  const [selectedTrade, setSelectedTrade] = useState<any>(null)
  const [showDetails, setShowDetails] = useState(false)

  useEffect(() => {
    const loadData = async () => {
      if (!symbol) return
      setLoading(true)
      try {
        const [ohlc, smaData, atrData] = await Promise.all([
          fetchAssetOhlcv(symbol),
          fetchSMA(symbol, 20),
          fetchATR(symbol, 14),
        ])
        setOhlcv(ohlc.data)
        setSma(smaData)
        setAtr(atrData)
      } catch (err) {
        console.error('Asset detail load failed:', err)
      } finally {
        setLoading(false)
      }
    }
    loadData()
  }, [symbol])

  useEffect(() => {
    const loadPositions = async () => {
      try {
        const [posRes, tradeRes, marketRes] = await Promise.all([
          fetch('/api/v1/positions/open?symbol=' + symbol).then(r => r.json()),
          fetch('/api/v1/positions?symbol=' + symbol + '&status=CLOSED').then(r => r.json()),
          fetch('/api/v1/monitor/market-status').then(r => r.json()),
        ])
        setPositions(posRes)
        setTrades(tradeRes)
        setMarketStatus(marketRes)
      } catch (err) {
        console.error('Failed to load positions:', err)
      }
    }
    loadPositions()
  }, [symbol])

  const runStrategy = async () => {
    setRunning(true)
    setError(null)
    try {
      const res = await fetch('/api/v1/positions/strategy-calculations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol,
          fast_sma: fastSma,
          slow_sma: slowSma,
          atr_window: atrWindow,
          atr_multiplier: atrMultiplier,
          cost_bps: costBps,
          start_date: startDate,
          end_date: endDate,
        }),
      })
      if (!res.ok) throw new Error('Strategy calculation failed')
      const data = await res.json()
      setStrategyResult(data)
    } catch (err: any) {
      setError(err.message || 'Failed to run strategy')
    } finally {
      setRunning(false)
    }
  }

  const addPosition = async (trade: any) => {
    try {
      const res = await fetch('/api/v1/positions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol,
          signal_date: trade.entry_date,
          entry_date: trade.entry_date,
          entry_price: trade.entry_price,
          fast_sma,
          slow_sma,
          atr_window: atrWindow,
          atr_multiplier: atrMultiplier,
          cost_bps,
        }),
      })
      if (!res.ok) throw new Error('Failed to add position')
      // Refresh positions
      const posRes = await fetch('/api/v1/positions/open?symbol=' + symbol).then(r => r.json())
      setPositions(posRes)
    } catch (err: any) {
      alert('Failed to add position: ' + err.message)
    }
  }

  const closePosition = async (positionId: number, exitPrice: number, reason: string) => {
    try {
      const today = new Date().toISOString().split('T')[0]
      const res = await fetch(`/api/v1/positions/${positionId}/close?exit_date=${today}&exit_price=${exitPrice}&exit_reason=${reason}`, {
        method: 'POST',
      })
      if (!res.ok) throw new Error('Failed to close position')
      // Refresh positions and trades
      const [posRes, tradeRes] = await Promise.all([
        fetch('/api/v1/positions/open?symbol=' + symbol).then(r => r.json()),
        fetch('/api/v1/positions?symbol=' + symbol + '&status=CLOSED').then(r => r.json()),
      ])
      setPositions(posRes)
      setTrades(tradeRes)
    } catch (err: any) {
      alert('Failed to close position: ' + err.message)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-slate-400">Loading {symbol}...</div>
      </div>
    )
  }

  const latestBar = ohlcv[ohlcv.length - 1]
  const prevBar = ohlcv[ohlcv.length - 2]
  const change = latestBar ? latestBar.close - (prevBar?.close || 0) : 0
  const pctChange = prevBar ? (change / prevBar.close) * 100 : 0

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-2xl font-semibold text-slate-100">{symbol}</h1>
          <div className="flex items-center gap-4 mt-2">
            {latestBar && (
              <>
                <span className="text-3xl font-bold text-slate-100">₹{latestBar.close.toFixed(2)}</span>
                <span className={`text-lg ${change >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {change >= 0 ? '+' : ''}{change.toFixed(2)} ({pctChange >= 0 ? '+' : ''}{pctChange.toFixed(2)}%)
                </span>
              </>
            )}
          </div>
          {marketStatus && (
            <div className="text-xs text-slate-500 mt-1">
              {marketStatus.is_open ? '🟢 Market Open' : '🔴 Market Closed'} | {marketStatus.current_time_ist}
            </div>
          )}
        </div>
        <div className="text-right text-sm text-slate-400">
          <div>Bars: {ohlcv.length}</div>
          {ohlcv.length > 0 && (
            <div className="text-xs">
              {ohlcv[0].time} to {ohlcv[ohlcv.length - 1].time}
            </div>
          )}
        </div>
      </div>

      {/* Chart */}
      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
        <CandlestickChart data={ohlcv} symbol={symbol} />
      </div>

      {/* Strategy Panel */}
      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
        <h2 className="text-lg font-semibold text-slate-100 mb-4">Strategy Configuration</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
          <div>
            <label className="block text-slate-300 text-sm mb-2">Fast SMA</label>
            <input
              type="number"
              value={fastSma}
              onChange={(e) => setFastSma(Number(e.target.value))}
              className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-slate-100"
            />
          </div>
          <div>
            <label className="block text-slate-300 text-sm mb-2">Slow SMA</label>
            <input
              type="number"
              value={slowSma}
              onChange={(e) => setSlowSma(Number(e.target.value))}
              className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-slate-100"
            />
          </div>
          <div>
            <label className="block text-slate-300 text-sm mb-2">ATR Window</label>
            <input
              type="number"
              value={atrWindow}
              onChange={(e) => setAtrWindow(Number(e.target.value))}
              className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-slate-100"
            />
          </div>
          <div>
            <label className="block text-slate-300 text-sm mb-2">ATR Multiplier</label>
            <input
              type="number"
              step="0.1"
              value={atrMultiplier}
              onChange={(e) => setAtrMultiplier(Number(e.target.value))}
              className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-slate-100"
            />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label className="block text-slate-300 text-sm mb-2">Start Date</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-slate-100"
            />
          </div>
          <div>
            <label className="block text-slate-300 text-sm mb-2">End Date</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-slate-100"
            />
          </div>
        </div>
        <div className="flex justify-end">
          <button
            onClick={runStrategy}
            disabled={running}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 disabled:cursor-not-allowed text-white px-6 py-2 rounded-md font-medium"
          >
            {running ? 'Running...' : 'Run Strategy'}
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-rose-950/50 border border-rose-800 text-rose-200 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      {/* Strategy Results */}
      {strategyResult && (
        <>
          {/* Signals Summary */}
          <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
            <h2 className="text-lg font-semibold text-slate-100 mb-4">Strategy Signals</h2>
            <div className="grid grid-cols-3 gap-4 mb-4">
              <div className="bg-slate-800/50 rounded p-3">
                <div className="text-slate-400 text-xs">Total Signals</div>
                <div className="text-2xl font-bold text-slate-100">{strategyResult.signals.length}</div>
              </div>
              <div className="bg-slate-800/50 rounded p-3">
                <div className="text-slate-400 text-xs">Trades</div>
                <div className="text-2xl font-bold text-slate-100">{strategyResult.trades.length}</div>
              </div>
              <div className="bg-slate-800/50 rounded p-3">
                <div className="text-slate-400 text-xs">Win Rate</div>
                <div className="text-2xl font-bold text-emerald-400">
                  {strategyResult.trades.length > 0
                    ? ((strategyResult.trades.filter(t => t.net_pnl > 0).length / strategyResult.trades.length) * 100).toFixed(1)
                    : 0}%
                </div>
              </div>
            </div>
            
            {/* Trade List */}
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-slate-400 border-b border-slate-800">
                    <th className="text-left px-3 py-2">#</th>
                    <th className="text-left px-3 py-2">Entry Date</th>
                    <th className="text-right px-3 py-2">Entry Price</th>
                    <th className="text-left px-3 py-2">Exit Date</th>
                    <th className="text-right px-3 py-2">Exit Price</th>
                    <th className="text-left px-3 py-2">Reason</th>
                    <th className="text-right px-3 py-2">Net P&L</th>
                    <th className="text-center px-3 py-2">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {strategyResult.trades.map((trade, idx) => (
                    <tr key={idx} className="border-b border-slate-800/50 hover:bg-slate-800/30">
                      <td className="px-3 py-2 text-slate-500">{idx + 1}</td>
                      <td className="px-3 py-2 text-slate-300 font-mono text-xs">{trade.entry_date}</td>
                      <td className="px-3 py-2 text-right text-slate-300">₹{trade.entry_price.toFixed(2)}</td>
                      <td className="px-3 py-2 text-slate-300 font-mono text-xs">{trade.exit_date}</td>
                      <td className="px-3 py-2 text-right text-slate-300">₹{trade.exit_price.toFixed(2)}</td>
                      <td className="px-3 py-2 text-slate-400 text-xs">{trade.exit_reason}</td>
                      <td className={`px-3 py-2 text-right font-medium ${trade.net_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {trade.net_pnl >= 0 ? '+' : ''}{trade.net_pnl.toFixed(2)}%
                      </td>
                      <td className="px-3 py-2 text-center">
                        <button
                          onClick={() => { setSelectedTrade(trade); setShowDetails(true); }}
                          className="text-blue-400 hover:text-blue-300 text-xs"
                        >
                          Details
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Calculation Table */}
          <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
            <h2 className="text-lg font-semibold text-slate-100 mb-4">Historical Calculations</h2>
            <div className="overflow-x-auto max-h-96">
              <table className="w-full text-xs">
                <thead className="sticky top-0 bg-slate-900">
                  <tr className="text-slate-400 border-b border-slate-800">
                    <th className="text-left px-2 py-1">Date</th>
                    <th className="text-right px-2 py-1">Open</th>
                    <th className="text-right px-2 py-1">High</th>
                    <th className="text-right px-2 py-1">Low</th>
                    <th className="text-right px-2 py-1">Close</th>
                    <th className="text-right px-2 py-1">SMA F</th>
                    <th className="text-right px-2 py-1">SMA S</th>
                    <th className="text-right px-2 py-1">ATR</th>
                    <th className="text-center px-2 py-1">Signal</th>
                    <th className="text-center px-2 py-1">Position</th>
                    <th className="text-right px-2 py-1">Stop</th>
                  </tr>
                </thead>
                <tbody>
                  {strategyResult.calculations.map((calc, idx) => (
                    <tr key={idx} className={`border-b border-slate-800/30 ${
                      calc.signal === 'BUY' ? 'bg-emerald-950/20' :
                      calc.signal === 'SELL' ? 'bg-rose-950/20' : ''
                    }`}>
                      <td className="px-2 py-1 text-slate-400 font-mono">{calc.date}</td>
                      <td className="px-2 py-1 text-right text-slate-300">₹{calc.open.toFixed(2)}</td>
                      <td className="px-2 py-1 text-right text-emerald-400">₹{calc.high.toFixed(2)}</td>
                      <td className="px-2 py-1 text-right text-rose-400">₹{calc.low.toFixed(2)}</td>
                      <td className={`px-2 py-1 text-right font-medium ${calc.close >= calc.open ? 'text-emerald-400' : 'text-rose-400'}`}>
                        ₹{calc.close.toFixed(2)}
                      </td>
                      <td className="px-2 py-1 text-right text-slate-400">{calc.fast_sma?.toFixed(2) || '-'}</td>
                      <td className="px-2 py-1 text-right text-slate-400">{calc.slow_sma?.toFixed(2) || '-'}</td>
                      <td className="px-2 py-1 text-right text-slate-400">{calc.atr?.toFixed(2) || '-'}</td>
                      <td className="px-2 py-1 text-center">
                        {calc.signal === 'BUY' && (
                          <span className="bg-emerald-900/50 text-emerald-400 px-2 py-0.5 rounded text-xs">BUY</span>
                        )}
                        {calc.signal === 'SELL' && (
                          <span className="bg-rose-900/50 text-rose-400 px-2 py-0.5 rounded text-xs">SELL</span>
                        )}
                        {calc.signal === 'HOLD' && (
                          <span className="text-slate-600">-</span>
                        )}
                      </td>
                      <td className="px-2 py-1 text-center">
                        {calc.position === 'OPEN' && (
                          <span className="bg-blue-900/50 text-blue-400 px-2 py-0.5 rounded text-xs">OPEN</span>
                        )}
                        {calc.position === 'CLOSED' && (
                          <span className="bg-slate-700 text-slate-400 px-2 py-0.5 rounded text-xs">CLOSED</span>
                        )}
                        {!calc.position && (
                          <span className="text-slate-600">-</span>
                        )}
                      </td>
                      <td className="px-2 py-1 text-right text-rose-400">{calc.stop_price?.toFixed(2) || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {/* Active Positions */}
      {positions.length > 0 && (
        <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
          <h2 className="text-lg font-semibold text-slate-100 mb-4">Active Positions</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-slate-400 border-b border-slate-800">
                  <th className="text-left px-3 py-2">Signal Date</th>
                  <th className="text-left px-3 py-2">Entry Date</th>
                  <th className="text-right px-3 py-2">Entry Price</th>
                  <th className="text-right px-3 py-2">Current</th>
                  <th className="text-right px-3 py-2">Stop</th>
                  <th className="text-right px-3 py-2">Unrealized P&L</th>
                  <th className="text-center px-3 py-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {positions.map((pos) => {
                  const unrealizedPnl = pos.current_price ? ((pos.current_price - pos.entry_price) / pos.entry_price) * 100 : 0
                  return (
                    <tr key={pos.id} className="border-b border-slate-800/50">
                      <td className="px-3 py-2 text-slate-400 font-mono text-xs">{pos.signal_date}</td>
                      <td className="px-3 py-2 text-slate-300 font-mono text-xs">{pos.entry_date}</td>
                      <td className="px-3 py-2 text-right text-slate-300">₹{pos.entry_price.toFixed(2)}</td>
                      <td className="px-3 py-2 text-right text-slate-300">₹{pos.current_price?.toFixed(2) || '-'}</td>
                      <td className="px-3 py-2 text-right text-rose-400">₹{pos.stop_price?.toFixed(2) || '-'}</td>
                      <td className={`px-3 py-2 text-right font-medium ${unrealizedPnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {unrealizedPnl >= 0 ? '+' : ''}{unrealizedPnl.toFixed(2)}%
                      </td>
                      <td className="px-3 py-2 text-center">
                        <button
                          onClick={() => {
                            if (latestBar) {
                              closePosition(pos.id, latestBar.close, 'manual')
                            }
                          }}
                          className="bg-rose-600 hover:bg-rose-700 text-white px-3 py-1 rounded text-xs"
                        >
                          Close
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Trade History */}
      {trades.length > 0 && (
        <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
          <h2 className="text-lg font-semibold text-slate-100 mb-4">Trade History</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-slate-400 border-b border-slate-800">
                  <th className="text-left px-3 py-2">Entry Date</th>
                  <th className="text-right px-3 py-2">Entry Price</th>
                  <th className="text-left px-3 py-2">Exit Date</th>
                  <th className="text-right px-3 py-2">Exit Price</th>
                  <th className="text-left px-3 py-2">Reason</th>
                  <th className="text-right px-3 py-2">Gross P&L</th>
                  <th className="text-right px-3 py-2">Cost</th>
                  <th className="text-right px-3 py-2">Net P&L</th>
                </tr>
              </thead>
              <tbody>
                {trades.map((trade, idx) => (
                  <tr key={idx} className="border-b border-slate-800/50 hover:bg-slate-800/30">
                    <td className="px-3 py-2 text-slate-300 font-mono text-xs">{trade.entry_date}</td>
                    <td className="px-3 py-2 text-right text-slate-300">₹{trade.entry_price.toFixed(2)}</td>
                    <td className="px-3 py-2 text-slate-300 font-mono text-xs">{trade.exit_date}</td>
                    <td className="px-3 py-2 text-right text-slate-300">₹{trade.exit_price.toFixed(2)}</td>
                    <td className="px-3 py-2 text-slate-400 text-xs">{trade.exit_reason}</td>
                    <td className={`px-3 py-2 text-right ${trade.gross_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {trade.gross_pnl >= 0 ? '+' : ''}{trade.gross_pnl.toFixed(2)}%
                    </td>
                    <td className="px-3 py-2 text-right text-slate-500">{trade.cost.toFixed(2)}%</td>
                    <td className={`px-3 py-2 text-right font-medium ${trade.net_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {trade.net_pnl >= 0 ? '+' : ''}{trade.net_pnl.toFixed(2)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Calculation Details Modal */}
      {showDetails && selectedTrade && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-slate-900 border border-slate-700 rounded-lg p-6 max-w-2xl w-full max-h-[80vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold text-slate-100">Trade Details</h3>
              <button onClick={() => setShowDetails(false)} className="text-slate-400 hover:text-slate-200">
                ✕
              </button>
            </div>
            <div className="space-y-4 text-sm">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <span className="text-slate-400">Entry Date:</span>
                  <span className="text-slate-200 ml-2 font-mono">{selectedTrade.entry_date}</span>
                </div>
                <div>
                  <span className="text-slate-400">Entry Price:</span>
                  <span className="text-slate-200 ml-2">₹{selectedTrade.entry_price.toFixed(2)}</span>
                </div>
                <div>
                  <span className="text-slate-400">Exit Date:</span>
                  <span className="text-slate-200 ml-2 font-mono">{selectedTrade.exit_date}</span>
                </div>
                <div>
                  <span className="text-slate-400">Exit Price:</span>
                  <span className="text-slate-200 ml-2">₹{selectedTrade.exit_price.toFixed(2)}</span>
                </div>
                <div>
                  <span className="text-slate-400">Stop Price:</span>
                  <span className="text-rose-400 ml-2">₹{selectedTrade.stop_price?.toFixed(2) || '-'}</span>
                </div>
                <div>
                  <span className="text-slate-400">Exit Reason:</span>
                  <span className="text-slate-200 ml-2">{selectedTrade.exit_reason}</span>
                </div>
              </div>
              <div className="pt-4 border-t border-slate-800">
                <h4 className="text-slate-300 font-medium mb-2">P&L Breakdown</h4>
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <span className="text-slate-400">Gross P&L:</span>
                    <span className={`ml-2 ${selectedTrade.gross_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {selectedTrade.gross_pnl >= 0 ? '+' : ''}{selectedTrade.gross_pnl.toFixed(2)}%
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400">Transaction Cost:</span>
                    <span className="text-slate-200 ml-2">{selectedTrade.cost.toFixed(2)}%</span>
                  </div>
                  <div>
                    <span className="text-slate-400">Net P&L:</span>
                    <span className={`ml-2 font-medium ${selectedTrade.net_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {selectedTrade.net_pnl >= 0 ? '+' : ''}{selectedTrade.net_pnl.toFixed(2)}%
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
