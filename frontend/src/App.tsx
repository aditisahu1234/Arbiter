import { useEffect, useState, useCallback } from 'react'
import { Header } from './components/Header'
import { UniverseBar } from './components/UniverseBar'
import { AssetTable } from './components/AssetTable'
import { CandlestickChart } from './components/CandlestickChart'
import { OhlcvTable } from './components/OhlcvTable'
import {
  fetchAssets,
  fetchAssetOhlcv,
  fetchLakehouseStatus,
  fetchUniverses,
  triggerIngestion,
} from './services/api'
import { Asset, LakehouseStatus, OhlcBar, Universe } from './types'

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

export default function App() {
  const [universes, setUniverses] = useState<Universe[]>([])
  const [selectedUniverse, setSelectedUniverse] = useState<string>('')
  const [assets, setAssets] = useState<Asset[]>([])
  const [totalAssets, setTotalAssets] = useState<number>(0)
  const [searchTerm, setSearchTerm] = useState<string>('')
  const [selectedSymbol, setSelectedSymbol] = useState<string>('RELIANCE')
  const [ohlcvData, setOhlcvData] = useState<OhlcBar[]>([])
  const [lakehouseStatus, setLakehouseStatus] = useState<LakehouseStatus | null>(null)
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false)
  const [ingestingSymbol, setIngestingSymbol] = useState<string | null>(null)
  const [notification, setNotification] = useState<string | null>(null)
  
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
  const [positions, setPositions] = useState<Position[]>([])
  const [trades, setTrades] = useState<Trade[]>([])
  const [marketStatus, setMarketStatus] = useState<MarketStatus | null>(null)
  const [selectedTrade, setSelectedTrade] = useState<Trade | null>(null)
  const [showDetails, setShowDetails] = useState(false)

  // Load Universes & Lakehouse telemetry
  const loadInitialData = useCallback(async () => {
    setIsRefreshing(true)
    try {
      const [uData, lData] = await Promise.all([
        fetchUniverses(),
        fetchLakehouseStatus(),
      ])
      setUniverses(uData)
      setLakehouseStatus(lData)
    } catch (err) {
      console.error('Error fetching initial platform data:', err)
    } finally {
      setIsRefreshing(false)
    }
  }, [])

  useEffect(() => {
    loadInitialData()
  }, [loadInitialData])

  // Load Assets when universe or search changes
  useEffect(() => {
    const handler = setTimeout(async () => {
      try {
        const res = await fetchAssets({
          universe: selectedUniverse || undefined,
          search: searchTerm || undefined,
          limit: 100,
        })
        setAssets(res.items)
        setTotalAssets(res.total)
      } catch (err) {
        console.error('Error loading assets:', err)
      }
    }, 200)

    return () => clearTimeout(handler)
  }, [selectedUniverse, searchTerm])

  // Load OHLCV when selected asset changes
  const loadOhlcv = useCallback(async (symbol: string) => {
    try {
      const res = await fetchAssetOhlcv(symbol)
      setOhlcvData(res.data)
    } catch (err) {
      console.error(`Error loading OHLCV for ${symbol}:`, err)
      setOhlcvData([])
    }
  }, [])

  useEffect(() => {
    if (selectedSymbol) {
      loadOhlcv(selectedSymbol)
      loadPositions(selectedSymbol)
    }
  }, [selectedSymbol, loadOhlcv])

  const loadPositions = useCallback(async (symbol: string) => {
    try {
      const [posRes, tradeRes, marketRes] = await Promise.all([
        fetch(`/api/v1/positions/open?symbol=${symbol}`).then(r => r.json()),
        fetch(`/api/v1/positions?symbol=${symbol}&status=CLOSED`).then(r => r.json()),
        fetch('/api/v1/monitor/market-status').then(r => r.json()),
      ])
      setPositions(posRes)
      setTrades(tradeRes)
      setMarketStatus(marketRes)
    } catch (err) {
      console.error('Failed to load positions:', err)
    }
  }, [])

  // Trigger dynamic ingestion
  const handleIngest = async (symbol: string) => {
    setIngestingSymbol(symbol)
    setNotification(`Fetching 5-year historical market data for ${symbol} from Yahoo Finance...`)
    try {
      const res = await triggerIngestion(symbol)
      if (res.status === 'success') {
        setNotification(
          `Successfully ingested ${res.rows_ingested} daily bars for ${symbol} into Parquet Lakehouse!`
        )
        // Refresh telemetry and reload asset OHLCV
        const lData = await fetchLakehouseStatus()
        setLakehouseStatus(lData)
        setSelectedSymbol(symbol)
        await loadOhlcv(symbol)
        await loadPositions(symbol)

        // Refresh asset table
        const aRes = await fetchAssets({
          universe: selectedUniverse || undefined,
          search: searchTerm || undefined,
          limit: 100,
        })
        setAssets(aRes.items)
      } else {
        setNotification(`Ingestion response: ${res.status}. Check backend logs.`)
      }
    } catch (err: any) {
      setNotification(`Failed to ingest ${symbol}: ${err.message}`)
    } finally {
      setIngestingSymbol(null)
      setTimeout(() => setNotification(null), 5000)
    }
  }

  const runStrategy = async () => {
    setRunning(true)
    setError(null)
    try {
      const res = await fetch('/api/v1/positions/strategy-calculations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol: selectedSymbol,
          fast_sma: fastSma,
          slow_sma: slowSma,
          atr_window: atrWindow,
          atr_multiplier: atrMultiplier,
          cost_bps: costBps,
          start_date: startDate,
          end_date: endDate,
        }),
      })
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}))
        throw new Error(errData.detail || `Strategy calculation failed (${res.status})`)
      }
      const data = await res.json()
      setStrategyResult(data)
    } catch (err: any) {
      setError(err.message || 'Failed to run strategy')
    } finally {
      setRunning(false)
    }
  }

  const addPosition = async (trade: Trade) => {
    try {
      const res = await fetch('/api/v1/positions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol: selectedSymbol,
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
      await loadPositions(selectedSymbol)
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
      await loadPositions(selectedSymbol)
    } catch (err: any) {
      alert('Failed to close position: ' + err.message)
    }
  }

  const latestBar = ohlcvData[ohlcvData.length - 1]
  const prevBar = ohlcvData[ohlcvData.length - 2]
  const change = latestBar ? latestBar.close - (prevBar?.close || 0) : 0
  const pctChange = prevBar ? (change / prevBar.close) * 100 : 0

  return (
    <div className="min-h-screen bg-[#0a0d14] text-slate-100 flex flex-col font-sans selection:bg-blue-600 selection:text-white">
      {/* Top Telemetry Header */}
      <Header
        status={lakehouseStatus}
        onRefresh={loadInitialData}
        isRefreshing={isRefreshing}
      />

      {/* Universe Filter Bar */}
      <UniverseBar
        universes={universes}
        selectedUniverse={selectedUniverse}
        onSelectUniverse={setSelectedUniverse}
        totalCatalogAssets={512}
      />

      {/* Dynamic Toast / Status Banner */}
      {notification && (
        <div className="bg-blue-950/80 border-b border-blue-800 text-blue-200 px-6 py-2 text-xs font-mono flex items-center justify-between transition-all">
          <span>{notification}</span>
          <button
            onClick={() => setNotification(null)}
            className="text-slate-400 hover:text-white ml-4"
          >
            ✕
          </button>
        </div>
      )}

      {/* Main Terminal Workspace */}
      <main className="flex-1 p-6 grid grid-cols-1 xl:grid-cols-12 gap-6 overflow-auto">
        {/* Left Column: Asset Selection Table */}
        <section className="xl:col-span-3 flex flex-col h-full">
          <AssetTable
            assets={assets}
            total={totalAssets}
            selectedSymbol={selectedSymbol}
            onSelectSymbol={setSelectedSymbol}
            onIngest={handleIngest}
            ingestingSymbol={ingestingSymbol}
            searchTerm={searchTerm}
            onSearchChange={setSearchTerm}
          />
        </section>

        {/* Center Column: Chart & OHLCV */}
        <section className="xl:col-span-5 flex flex-col space-y-6">
          {/* Header with price info */}
          <div className="flex justify-between items-start">
            <div>
              <h1 className="text-2xl font-semibold text-slate-100">{selectedSymbol}</h1>
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
              <div>Bars: {ohlcvData.length}</div>
              {ohlcvData.length > 0 && (
                <div className="text-xs">
                  {ohlcvData[0].time} to {ohlcvData[ohlcvData.length - 1].time}
                </div>
              )}
            </div>
          </div>

          <CandlestickChart data={ohlcvData} symbol={selectedSymbol} />
          <OhlcvTable data={ohlcvData} />
        </section>

        {/* Right Column: Strategy Panel */}
        <section className="xl:col-span-4 flex flex-col space-y-6">
          {/* Strategy Configuration Panel */}
          <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
            <h2 className="text-lg font-semibold text-slate-100 mb-4">Strategy Configuration</h2>
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-300 text-xs mb-1">Fast SMA</label>
                  <input
                    type="number"
                    value={fastSma}
                    onChange={(e) => setFastSma(Number(e.target.value))}
                    className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-slate-100 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-slate-300 text-xs mb-1">Slow SMA</label>
                  <input
                    type="number"
                    value={slowSma}
                    onChange={(e) => setSlowSma(Number(e.target.value))}
                    className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-slate-100 text-sm"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-300 text-xs mb-1">ATR Window</label>
                  <input
                    type="number"
                    value={atrWindow}
                    onChange={(e) => setAtrWindow(Number(e.target.value))}
                    className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-slate-100 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-slate-300 text-xs mb-1">ATR Multiplier</label>
                  <input
                    type="number"
                    step="0.1"
                    value={atrMultiplier}
                    onChange={(e) => setAtrMultiplier(Number(e.target.value))}
                    className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-slate-100 text-sm"
                  />
                </div>
              </div>
              <div>
                <label className="block text-slate-300 text-xs mb-1">Transaction Cost (bps)</label>
                <input
                  type="number"
                  value={costBps}
                  onChange={(e) => setCostBps(Number(e.target.value))}
                  className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-slate-100 text-sm"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-300 text-xs mb-1">Start Date</label>
                  <input
                    type="date"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-slate-100 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-slate-300 text-xs mb-1">End Date</label>
                  <input
                    type="date"
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-slate-100 text-sm"
                  />
                </div>
              </div>
              <button
                onClick={runStrategy}
                disabled={running}
                className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 disabled:cursor-not-allowed text-white px-4 py-2 rounded-md font-medium transition-colors"
              >
                {running ? 'Calculating...' : 'RUN STRATEGY'}
              </button>
            </div>
          </div>

          {error && (
            <div className="bg-rose-950/50 border border-rose-800 text-rose-200 px-4 py-3 rounded-lg text-sm">
              {error}
            </div>
          )}

          {/* Strategy Results */}
          {strategyResult && (
            <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
              <h2 className="text-lg font-semibold text-slate-100 mb-4">Strategy Results</h2>
              
              {/* Summary */}
              <div className="grid grid-cols-3 gap-3 mb-4">
                <div className="bg-slate-800/50 rounded p-2 text-center">
                  <div className="text-slate-400 text-xs">Signals</div>
                  <div className="text-xl font-bold text-slate-100">{strategyResult.signals.length}</div>
                </div>
                <div className="bg-slate-800/50 rounded p-2 text-center">
                  <div className="text-slate-400 text-xs">Trades</div>
                  <div className="text-xl font-bold text-slate-100">{strategyResult.trades.length}</div>
                </div>
                <div className="bg-slate-800/50 rounded p-2 text-center">
                  <div className="text-slate-400 text-xs">Win Rate</div>
                  <div className="text-xl font-bold text-emerald-400">
                    {strategyResult.trades.length > 0
                      ? ((strategyResult.trades.filter(t => t.net_pnl > 0).length / strategyResult.trades.length) * 100).toFixed(0)
                      : 0}%
                  </div>
                </div>
              </div>

              {/* Trade List */}
              <div className="overflow-x-auto max-h-64">
                <table className="w-full text-xs">
                  <thead className="sticky top-0 bg-slate-900">
                    <tr className="text-slate-400 border-b border-slate-800">
                      <th className="text-left px-2 py-1">#</th>
                      <th className="text-left px-2 py-1">Entry</th>
                      <th className="text-right px-2 py-1">Price</th>
                      <th className="text-left px-2 py-1">Exit</th>
                      <th className="text-right px-2 py-1">P&L</th>
                      <th className="text-center px-2 py-1">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {strategyResult.trades.map((trade, idx) => (
                      <tr key={idx} className="border-b border-slate-800/30 hover:bg-slate-800/30">
                        <td className="px-2 py-1 text-slate-500">{idx + 1}</td>
                        <td className="px-2 py-1 text-slate-400 font-mono">{trade.entry_date}</td>
                        <td className="px-2 py-1 text-right text-slate-300">₹{trade.entry_price.toFixed(0)}</td>
                        <td className="px-2 py-1 text-slate-400 font-mono">{trade.exit_date}</td>
                        <td className={`px-2 py-1 text-right font-medium ${trade.net_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                          {trade.net_pnl >= 0 ? '+' : ''}{trade.net_pnl.toFixed(1)}%
                        </td>
                        <td className="px-2 py-1 text-center">
                          <button
                            onClick={() => { setSelectedTrade(trade); setShowDetails(true); }}
                            className="text-blue-400 hover:text-blue-300"
                          >
                            Details
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Calculation Table */}
              <div className="mt-4">
                <h3 className="text-sm font-medium text-slate-300 mb-2">Calculations</h3>
                <div className="overflow-x-auto max-h-96">
                  <table className="w-full text-xs">
                    <thead className="sticky top-0 bg-slate-900">
                      <tr className="text-slate-400 border-b border-slate-800">
                        <th className="text-left px-1 py-1">Date</th>
                        <th className="text-right px-1 py-1">Close</th>
                        <th className="text-right px-1 py-1">SMA F</th>
                        <th className="text-right px-1 py-1">SMA S</th>
                        <th className="text-right px-1 py-1">ATR</th>
                        <th className="text-center px-1 py-1">Signal</th>
                        <th className="text-center px-1 py-1">Pos</th>
                      </tr>
                    </thead>
                    <tbody>
                      {strategyResult.calculations.map((calc, idx) => (
                        <tr key={idx} className={`border-b border-slate-800/20 ${
                          calc.signal === 'BUY' ? 'bg-emerald-950/20' :
                          calc.signal === 'SELL' ? 'bg-rose-950/20' : ''
                        }`}>
                          <td className="px-1 py-0.5 text-slate-500 font-mono">{calc.date}</td>
                          <td className="px-1 py-0.5 text-right text-slate-300">₹{calc.close.toFixed(0)}</td>
                          <td className="px-1 py-0.5 text-right text-amber-400">{calc.fast_sma?.toFixed(0) || '-'}</td>
                          <td className="px-1 py-0.5 text-right text-purple-400">{calc.slow_sma?.toFixed(0) || '-'}</td>
                          <td className="px-1 py-0.5 text-right text-slate-400">{calc.atr?.toFixed(0) || '-'}</td>
                          <td className="px-1 py-0.5 text-center">
                            {calc.signal === 'BUY' && (
                              <span className="bg-emerald-900/50 text-emerald-400 px-1 py-0.5 rounded text-xs">BUY</span>
                            )}
                            {calc.signal === 'SELL' && (
                              <span className="bg-rose-900/50 text-rose-400 px-1 py-0.5 rounded text-xs">SELL</span>
                            )}
                            {calc.signal === 'HOLD' && (
                              <span className="text-slate-600">-</span>
                            )}
                          </td>
                          <td className="px-1 py-0.5 text-center">
                            {calc.position === 'OPEN' && (
                              <span className="bg-blue-900/50 text-blue-400 px-1 py-0.5 rounded text-xs">OPEN</span>
                            )}
                            {calc.position === 'CLOSED' && (
                              <span className="bg-slate-700 text-slate-400 px-1 py-0.5 rounded text-xs">CLOSED</span>
                            )}
                            {!calc.position && (
                              <span className="text-slate-600">-</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* Active Positions */}
          {positions.length > 0 && (
            <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
              <h2 className="text-lg font-semibold text-slate-100 mb-4">Active Positions</h2>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-slate-400 border-b border-slate-800">
                      <th className="text-left px-2 py-1">Entry</th>
                      <th className="text-right px-2 py-1">Buy Price</th>
                      <th className="text-right px-2 py-1">Current</th>
                      <th className="text-right px-2 py-1">Stop</th>
                      <th className="text-right px-2 py-1">P&L</th>
                      <th className="text-center px-2 py-1">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {positions.map((pos) => {
                      const unrealizedPnl = pos.current_price ? ((pos.current_price - pos.entry_price) / pos.entry_price) * 100 : 0
                      return (
                        <tr key={pos.id} className="border-b border-slate-800/50">
                          <td className="px-2 py-1 text-slate-400 font-mono">{pos.entry_date}</td>
                          <td className="px-2 py-1 text-right text-slate-300">₹{pos.entry_price.toFixed(0)}</td>
                          <td className="px-2 py-1 text-right text-slate-300">₹{pos.current_price?.toFixed(0) || '-'}</td>
                          <td className="px-2 py-1 text-right text-rose-400">₹{pos.stop_price?.toFixed(0) || '-'}</td>
                          <td className={`px-2 py-1 text-right font-medium ${unrealizedPnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                            {unrealizedPnl >= 0 ? '+' : ''}{unrealizedPnl.toFixed(1)}%
                          </td>
                          <td className="px-2 py-1 text-center">
                            <button
                              onClick={() => {
                                if (latestBar) {
                                  closePosition(pos.id, latestBar.close, 'manual')
                                }
                              }}
                              className="bg-rose-600 hover:bg-rose-700 text-white px-2 py-0.5 rounded text-xs"
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
            <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
              <h2 className="text-lg font-semibold text-slate-100 mb-4">Trade History</h2>
              <div className="overflow-x-auto max-h-48">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-slate-400 border-b border-slate-800">
                      <th className="text-left px-2 py-1">Entry</th>
                      <th className="text-right px-2 py-1">Price</th>
                      <th className="text-left px-2 py-1">Exit</th>
                      <th className="text-right px-2 py-1">P&L</th>
                      <th className="text-left px-2 py-1">Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {trades.map((trade, idx) => (
                      <tr key={idx} className="border-b border-slate-800/50 hover:bg-slate-800/30">
                        <td className="px-2 py-1 text-slate-400 font-mono">{trade.entry_date}</td>
                        <td className="px-2 py-1 text-right text-slate-300">₹{trade.entry_price.toFixed(0)}</td>
                        <td className="px-2 py-1 text-slate-400 font-mono">{trade.exit_date}</td>
                        <td className={`px-2 py-1 text-right font-medium ${trade.net_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                          {trade.net_pnl >= 0 ? '+' : ''}{trade.net_pnl.toFixed(1)}%
                        </td>
                        <td className="px-2 py-1 text-slate-500">{trade.exit_reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </section>
      </main>

      {/* Calculation Details Modal */}
      {showDetails && selectedTrade && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-slate-900 border border-slate-700 rounded-lg p-6 max-w-lg w-full">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold text-slate-100">Trade Details</h3>
              <button onClick={() => setShowDetails(false)} className="text-slate-400 hover:text-slate-200">
                ✕
              </button>
            </div>
            <div className="space-y-3 text-sm">
              <div className="grid grid-cols-2 gap-3">
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
              <div className="pt-3 border-t border-slate-800">
                <h4 className="text-slate-300 font-medium mb-2">P&L Breakdown</h4>
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <span className="text-slate-400">Gross P&L:</span>
                    <span className={`ml-2 ${selectedTrade.gross_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {selectedTrade.gross_pnl >= 0 ? '+' : ''}{selectedTrade.gross_pnl.toFixed(2)}%
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400">Cost:</span>
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
