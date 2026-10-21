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
  fetchDataStatus,
  refreshAssetData,
  fetchLiveQuote,
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
  entry_date: string | null
  entry_price: number | null
  exit_date: string | null
  exit_price: number | null
  stop_price: number | null
  exit_reason: string | null
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
  selected_date: string | null
  selected_calculation: StrategyCalc | null
  next_session_recommendation: {
    symbol: string
    has_signal: boolean
    signal_date: string
    action: string | null
    expected_execution_basis: string
    stop_loss: number | null
    exit_note: string
    data_freshness: string
    reason?: string
    market_hours: {
      timezone: string
      current_time_ist: string
      market_open: boolean
      is_weekend: boolean
      session_open: string
      session_close: string
    } | null
  } | null
  data_status: {
    symbol: string
    has_data: boolean
    latest_date: string | null
    is_current: boolean
    market_status: string
    needs_refresh: boolean
  } | null
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
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [strategyDate, setStrategyDate] = useState('')
  const [running, setRunning] = useState(false)
  const [strategyResult, setStrategyResult] = useState<StrategyResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [resultsVisible, setResultsVisible] = useState(false)
  
  // Position state
  const [positions, setPositions] = useState<Position[]>([])
  const [trades, setTrades] = useState<Trade[]>([])
  const [marketStatus, setMarketStatus] = useState<MarketStatus | null>(null)
  const [selectedTrade] = useState<Trade | null>(null)
  const [showDetails, setShowDetails] = useState(false)
  const [dataStatus, setDataStatus] = useState<any>(null)

  interface LiveQuote {
    symbol: string
    price: number | null
    price_timestamp: string | null
    data_state: 'live' | 'delayed' | 'unavailable'
    is_intraday: boolean
    note?: string
    fallback_daily_date?: string | null
  }
  const [liveQuote, setLiveQuote] = useState<LiveQuote | null>(null)

  // Load a live/delayed intraday quote for the currently-selected asset when the
  // market is open, so the live BUY NOW situation can be shown with a verified
  // price. When the provider has no usable current-session value, data_state is
  // "unavailable" and we fall back to the last completed daily candle.
  useEffect(() => {
    if (!selectedSymbol) return
    let cancelled = false
    const load = async () => {
      try {
        const statusRes = await fetch('/api/v1/monitor/market-status').then(r => r.json())
        if (cancelled || !statusRes?.is_open) {
          setLiveQuote(null)
          return
        }
        const q = await fetchLiveQuote(selectedSymbol)
        if (!cancelled) setLiveQuote(q)
      } catch {
        if (!cancelled) setLiveQuote(null)
      }
    }
    load()
    return () => { cancelled = true }
  }, [selectedSymbol])

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

  const loadPositions = useCallback(async (symbol: string) => {
    try {
      const [posRes, tradeRes, marketRes, statusRes] = await Promise.all([
        fetch(`/api/v1/positions/open?symbol=${symbol}`).then(r => r.json()),
        fetch(`/api/v1/positions?symbol=${symbol}&status=CLOSED`).then(r => r.json()),
        fetch('/api/v1/monitor/market-status').then(r => r.json()),
        fetchDataStatus(symbol).catch(() => null),
      ])
      setPositions(posRes)
      setTrades(tradeRes)
      setMarketStatus(marketRes)
      setDataStatus(statusRes)
    } catch (err) {
      console.error('Failed to load positions:', err)
    }
  }, [])

  useEffect(() => {
    if (selectedSymbol) {
      loadOhlcv(selectedSymbol)
      loadPositions(selectedSymbol)
    }
  }, [selectedSymbol, loadOhlcv, loadPositions])

  // When OHLCV data arrives, set the default strategy interval to the stored data range.
  useEffect(() => {
    if (ohlcvData.length > 0) {
      setStartDate(ohlcvData[0].time)
      setEndDate(ohlcvData[ohlcvData.length - 1].time)
      setStrategyDate(ohlcvData[ohlcvData.length - 1].time)
    }
  }, [ohlcvData])

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
      // First check data freshness and refresh if needed
      const status = await fetchDataStatus(selectedSymbol)
      if (status && !status.is_current) {
        console.log(`Data is ${status.days_behind} days behind, refreshing...`)
        await refreshAssetData(selectedSymbol)
        // Reload OHLCV and positions after refresh
        await loadOhlcv(selectedSymbol)
        await loadPositions(selectedSymbol)
      }
      
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
          strategy_date: strategyDate,
        }),
      })
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}))
        throw new Error(errData.detail || `Strategy calculation failed (${res.status})`)
      }
      const data = await res.json()
      setStrategyResult(data)
      setResultsVisible(true)  // Show results after successful run
    } catch (err: any) {
      setError(err.message || 'Failed to run strategy')
    } finally {
      setRunning(false)
    }
  }

  const addPosition = async (calc: StrategyCalc, trade?: Trade) => {
    try {
      const signalDate = calc.date
      const entryDate = calc.entry_date || trade?.entry_date
      const entryPrice = calc.entry_price || trade?.entry_price

      if (!entryDate || !entryPrice) {
        setError('Missing entry details. Cannot add position.')
        return
      }

      const res = await fetch('/api/v1/positions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol: selectedSymbol,
          signal_date: signalDate,
          entry_date: entryDate,
          entry_price: entryPrice,
          fast_sma: fastSma,
          slow_sma: slowSma,
          atr_window: atrWindow,
          atr_multiplier: atrMultiplier,
          cost_bps: costBps,
        }),
      })
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}))
        throw new Error(errData.detail || 'Failed to add position')
      }
      await loadPositions(selectedSymbol)
    } catch (err: any) {
      setError('Failed to add position: ' + err.message)
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

      {/* Top Workspace: Asset Selection (1/3) + Chart (2/3) */}
      <div className="flex-1 p-6 grid grid-cols-1 xl:grid-cols-3 gap-6 items-start">
        {/* LEFT: Asset Selection (~1/3) */}
        <section className="xl:col-span-1">
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

        {/* RIGHT: Chart (~2/3) */}
        <section className="xl:col-span-2 flex flex-col space-y-6">
          {/* Company Header & Chart */}
          <div>
            <div className="flex justify-between items-start mb-4">
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
                {dataStatus && dataStatus.has_data && (
                  <div className="text-xs mt-1">
                    {dataStatus.is_current ? (
                      <span className="text-emerald-400">
                        ✓ Latest candle: {dataStatus.latest_date}
                        {dataStatus.provider_lagging ? (
                          <span className="text-slate-500"> · provider last published {dataStatus.provider_latest_date}</span>
                        ) : null}
                      </span>
                    ) : (
                      <span className="text-amber-400">
                        ⚠ Latest candle: {dataStatus.latest_date} · {dataStatus.trading_days_behind ?? dataStatus.days_behind} trading day(s) behind
                        {dataStatus.provider_lagging ? (
                          <span className="text-slate-500"> · provider last published {dataStatus.provider_latest_date}</span>
                        ) : null}
                      </span>
                    )}
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
          </div>
        </section>
      </div>

      {/* Lower Sections: Full Width */}
      <div className="flex-1 p-6 pt-0 grid grid-cols-1 gap-6">
        {/* OHLCV Data Table */}
        <OhlcvTable data={ohlcvData} />

          {/* Strategy Configuration & Results */}
          <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
            <h2 className="text-lg font-semibold text-slate-100 mb-4">Strategy Configuration</h2>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-4">
              <div>
                <label className="block text-slate-300 text-xs mb-1">Start Date</label>
                <input
                  type="date"
                  value={startDate}
                  max={endDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-slate-100 text-sm"
                />
              </div>
              <div>
                <label className="block text-slate-300 text-xs mb-1">End Date</label>
                <input
                  type="date"
                  value={endDate}
                  min={startDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-slate-100 text-sm"
                />
              </div>
              <div>
                <label className="block text-slate-300 text-xs mb-1">Strategy Date</label>
                <input
                  type="date"
                  value={strategyDate}
                  min={startDate}
                  max={endDate}
                  onChange={(e) => setStrategyDate(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-slate-100 text-sm"
                />
              </div>
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
              <div>
                <label className="block text-slate-300 text-xs mb-1">ATR Window</label>
                <input
                  type="number"
                  value={atrWindow}
                  onChange={(e) => setAtrWindow(Number(e.target.value))}
                  className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-slate-100 text-sm"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
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
              <div>
                <label className="block text-slate-300 text-xs mb-1">Cost (bps)</label>
                <input
                  type="number"
                  value={costBps}
                  onChange={(e) => setCostBps(Number(e.target.value))}
                  className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-slate-100 text-sm"
                />
              </div>
            </div>
            <div className="flex items-center justify-between">
              <button
                onClick={runStrategy}
                disabled={running}
                className="bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 disabled:cursor-not-allowed text-white px-6 py-2 rounded-md font-medium transition-colors"
              >
                {running ? 'Calculating...' : 'RUN STRATEGY'}
              </button>
              {strategyResult && (
                <button
                  onClick={() => setResultsVisible(!resultsVisible)}
                  className="bg-slate-700 hover:bg-slate-600 text-slate-200 px-4 py-2 rounded-md text-sm font-medium transition-colors"
                >
                  {resultsVisible ? 'Hide Results' : 'Show Results'}
                </button>
              )}
            </div>

            {error && (
              <div className="bg-rose-950/50 border border-rose-800 text-rose-200 px-4 py-3 rounded-lg text-sm mb-4">
                {error}
              </div>
            )}

            {/* Selected Date Result */}
            {strategyResult?.selected_calculation && (() => {
              const sel = strategyResult.selected_calculation!
              // Plain-English decision summary derived from the exact calculated values.
              const fastCfg = strategyResult.config?.fast_sma ?? 10
              const slowCfg = strategyResult.config?.slow_sma ?? 50
              const curRel = sel.fast_sma != null && sel.slow_sma != null
                ? (sel.fast_sma > sel.slow_sma ? 'above' : sel.fast_sma < sel.slow_sma ? 'below' : 'equal to')
                : 'unknown'
              const prevRel = sel.prev_fast_sma != null && sel.prev_slow_sma != null
                ? (sel.prev_fast_sma > sel.prev_slow_sma ? 'above' : sel.prev_fast_sma < sel.prev_slow_sma ? 'below' : 'equal to')
                : 'unknown'
              const decisionReason = (() => {
                if (sel.signal === 'BUY') {
                  return `The ${fastCfg}-day SMA crossed above the ${slowCfg}-day SMA. The strategy identifies a bullish crossover.`
                }
                if (sel.signal === 'SELL') {
                  return `The ${fastCfg}-day SMA fell below the ${slowCfg}-day SMA, triggering the strategy's exit condition.`
                }
                if (sel.position === 'OPEN') {
                  return `The ${fastCfg}-day SMA remains ${curRel} the ${slowCfg}-day SMA; a position is already open, so no new entry is recommended.`
                }
                if (curRel === 'above') {
                  return `The ${fastCfg}-day SMA remains above the ${slowCfg}-day SMA, but no new buy crossover occurred on this date.`
                }
                return `The ${fastCfg}-day SMA is ${curRel === 'unknown' ? 'unknown' : `below`} the ${slowCfg}-day SMA; the strategy currently has no open position.`
              })()
              const positionLabel = sel.position === 'OPEN' ? 'Open' : sel.position === 'CLOSED' ? 'Closed' : 'No position'
              const stopLabel = sel.stop_price != null ? `₹${Number(sel.stop_price).toFixed(2)} (suggested risk-control level)` : 'Not applicable'
              return (
              <div className="mt-4 bg-slate-800/50 border border-slate-700 rounded-lg p-4">
                <h3 className="text-md font-semibold text-slate-100 mb-1">
                  Latest Strategy Decision
                </h3>
                <p className="text-xs text-slate-400 mb-3">
                  Plain-English summary of the most recent completed calculation ({sel.date}). Detailed figures are shown below.
                </p>
                <div className="mb-4 p-3 rounded-md border border-slate-700 bg-slate-900/60">
                  <div className="flex items-center gap-3 mb-2">
                    <span className={`text-lg font-bold ${
                      sel.signal === 'BUY' ? 'text-emerald-400' : sel.signal === 'SELL' ? 'text-rose-400' : 'text-slate-200'
                    }`}>
                      {sel.signal === 'BUY' ? 'Buy' : sel.signal === 'SELL' ? 'Sell' : 'Hold'}
                    </span>
                    <span className="text-xs text-slate-500">{decisionReason}</span>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                    <div>
                      <span className="text-slate-400 block text-xs">Decision date</span>
                      <span className="text-slate-100 font-mono">{sel.date}</span>
                    </div>
                    <div>
                      <span className="text-slate-400 block text-xs">Market price (close)</span>
                      <span className="text-slate-100">₹{Number(sel.close).toFixed(2)}</span>
                    </div>
                    <div>
                      <span className="text-slate-400 block text-xs">Fast SMA ({fastCfg})</span>
                      <span className="text-amber-400">{sel.fast_sma != null ? `₹${Number(sel.fast_sma).toFixed(2)}` : 'Unavailable'}</span>
                    </div>
                    <div>
                      <span className="text-slate-400 block text-xs">Slow SMA ({slowCfg})</span>
                      <span className="text-purple-400">{sel.slow_sma != null ? `₹${Number(sel.slow_sma).toFixed(2)}` : 'Unavailable'}</span>
                    </div>
                    <div>
                      <span className="text-slate-400 block text-xs">Previous relationship</span>
                      <span className="text-slate-300">Fast SMA {prevRel} slow SMA</span>
                    </div>
                    <div>
                      <span className="text-slate-400 block text-xs">Current relationship</span>
                      <span className="text-slate-300">Fast SMA {curRel} slow SMA</span>
                    </div>
                    <div>
                      <span className="text-slate-400 block text-xs">Position state</span>
                      <span className="text-slate-100">{positionLabel}</span>
                    </div>
                    <div>
                      <span className="text-slate-400 block text-xs">Stop-loss</span>
                      <span className="text-rose-400">{stopLabel}</span>
                    </div>
                  </div>
                </div>

                <h4 className="text-sm font-semibold text-slate-200 mb-2">Detailed Calculations</h4>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                  <div>
                    <span className="text-slate-400">Market price (close):</span>
                    <span className="text-slate-200 ml-2">₹{Number(sel.close).toFixed(2)}</span>
                  </div>
                  <div>
                    <span className="text-slate-400">Fast SMA ({fastCfg}):</span>
                    <span className="text-amber-400 ml-2">{sel.fast_sma != null ? `₹${Number(sel.fast_sma).toFixed(2)}` : 'Unavailable'}</span>
                  </div>
                  <div>
                    <span className="text-slate-400">Slow SMA ({slowCfg}):</span>
                    <span className="text-purple-400 ml-2">{sel.slow_sma != null ? `₹${Number(sel.slow_sma).toFixed(2)}` : 'Unavailable'}</span>
                  </div>
                  <div>
                    <span className="text-slate-400">ATR:</span>
                    <span className="text-slate-200 ml-2">{sel.atr != null ? `₹${Number(sel.atr).toFixed(2)}` : 'Unavailable'}</span>
                  </div>
                  <div>
                    <span className="text-slate-400">Prev Fast SMA:</span>
                    <span className="text-amber-400 ml-2">{sel.prev_fast_sma != null ? `₹${Number(sel.prev_fast_sma).toFixed(2)}` : 'Unavailable'}</span>
                  </div>
                  <div>
                    <span className="text-slate-400">Prev Slow SMA:</span>
                    <span className="text-purple-400 ml-2">{sel.prev_slow_sma != null ? `₹${Number(sel.prev_slow_sma).toFixed(2)}` : 'Unavailable'}</span>
                  </div>
                  <div>
                    <span className="text-slate-400">Signal:</span>
                    <span className={`ml-2 font-medium ${
                      sel.signal === 'BUY' ? 'text-emerald-400' :
                      sel.signal === 'SELL' ? 'text-rose-400' :
                      'text-slate-400'
                    }`}>
                      {sel.signal}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400">Position:</span>
                    <span className="ml-2">
                      {sel.position === 'OPEN' ? (
                        <span className="text-blue-400">OPEN</span>
                      ) : sel.position === 'CLOSED' ? (
                        <span className="text-slate-400">CLOSED</span>
                      ) : (
                        <span className="text-slate-500">-</span>
                      )}
                    </span>
                  </div>
                </div>
                
                {/* Entry/Exit Details */}
                {sel.entry_price != null && (
                  <div className="mt-3 pt-3 border-t border-slate-700">
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                      <div>
                        <span className="text-slate-400">Entry Date:</span>
                        <span className="text-slate-200 ml-2 font-mono">{sel.entry_date || 'Unavailable'}</span>
                      </div>
                      <div>
                        <span className="text-slate-400">Entry Price:</span>
                        <span className="text-emerald-400 ml-2">₹{Number(sel.entry_price).toFixed(2)}</span>
                      </div>
                      <div>
                        <span className="text-slate-400">Stop Price:</span>
                        <span className="text-rose-400 ml-2">{sel.stop_price != null ? `₹${Number(sel.stop_price).toFixed(2)}` : 'Not applicable'}</span>
                      </div>
                      <div>
                        <span className="text-slate-400">Exit Date:</span>
                        <span className="text-slate-300 ml-2 font-mono">{sel.exit_date || 'Open'}</span>
                      </div>
                    </div>
                  </div>
                )}
                
                {/* Action Button for BUY signals */}
                {sel.signal === 'BUY' && sel.entry_date && (
                  <div className="mt-3">
                    <button
                      onClick={() => addPosition(sel)}
                      className="bg-emerald-600 hover:bg-emerald-700 text-white px-4 py-2 rounded-md text-sm font-medium"
                    >
                      ADD POSITION
                    </button>
                  </div>
                )}
              </div>
              )
            })()}

            {/* Detailed Strategy Results (collapsible via Show/Hide Results) */}
            {strategyResult && resultsVisible && (
              <div className="mt-4">
                <div className="grid grid-cols-3 gap-3 mb-4">
                  <div className="bg-slate-800/50 rounded p-3 text-center">
                    <div className="text-slate-400 text-xs">Signals</div>
                    <div className="text-xl font-bold text-slate-100">{strategyResult.signals.length}</div>
                  </div>
                  <div className="bg-slate-800/50 rounded p-3 text-center">
                    <div className="text-slate-400 text-xs">Trades</div>
                    <div className="text-xl font-bold text-slate-100">{strategyResult.trades.length}</div>
                  </div>
                  <div className="bg-slate-800/50 rounded p-3 text-center">
                    <div className="text-slate-400 text-xs">Win Rate</div>
                    <div className="text-xl font-bold text-emerald-400">
                      {strategyResult.trades.length > 0
                        ? ((strategyResult.trades.filter(t => t.net_pnl > 0).length / strategyResult.trades.length) * 100).toFixed(0)
                        : 0}%
                    </div>
                  </div>
                </div>

                {/* Calculation Table */}
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="text-slate-400 border-b border-slate-800">
                        <th className="text-left px-2 py-1">Date</th>
                        <th className="text-right px-2 py-1">Close</th>
                        <th className="text-right px-2 py-1">SMA Fast</th>
                        <th className="text-right px-2 py-1">SMA Slow</th>
                        <th className="text-right px-2 py-1">ATR</th>
                        <th className="text-center px-2 py-1">Signal</th>
                        <th className="text-center px-2 py-1">Position</th>
                        <th className="text-center px-2 py-1">Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {strategyResult.calculations.map((calc, idx) => (
                        <tr key={idx} className={`border-b border-slate-800/20 ${
                          calc.signal === 'BUY' ? 'bg-emerald-950/20' :
                          calc.signal === 'SELL' ? 'bg-rose-950/20' : ''
                        }`}>
                          <td className="px-2 py-1 text-slate-500 font-mono">{calc.date}</td>
                          <td className="px-2 py-1 text-right text-slate-300">₹{calc.close.toFixed(0)}</td>
                          <td className="px-2 py-1 text-right text-amber-400">{calc.fast_sma?.toFixed(0) || '-'}</td>
                          <td className="px-2 py-1 text-right text-purple-400">{calc.slow_sma?.toFixed(0) || '-'}</td>
                          <td className="px-2 py-1 text-right text-slate-400">{calc.atr?.toFixed(0) || '-'}</td>
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
                          <td className="px-2 py-1 text-center">
                            {calc.signal === 'BUY' && calc.entry_price && (
                              <button
                                onClick={() => addPosition(calc)}
                                className="bg-emerald-600 hover:bg-emerald-700 text-white px-2 py-0.5 rounded text-xs"
                              >
                                ADD
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>

          {/* Trade Recommendations — compact table of every completed trade in the selected run */}
          {strategyResult && (
            <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-slate-100">Trade Recommendations</h2>
                <span className="text-xs text-slate-400 bg-slate-800 px-3 py-1 rounded-full">
                  {strategyResult.trades.filter(t => t.exit_date && t.exit_price != null && t.exit_reason !== 'end_of_data').length} completed trade(s)
                </span>
              </div>
              {strategyResult.trades.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="text-slate-400 border-b border-slate-800">
                        <th className="text-left px-2 py-1">#</th>
                        <th className="text-left px-2 py-1">Symbol</th>
                        <th className="text-left px-2 py-1">Action</th>
                        <th className="text-left px-2 py-1">Buy Date</th>
                        <th className="text-right px-2 py-1">Buy Price</th>
                        <th className="text-left px-2 py-1">Sell Date</th>
                        <th className="text-right px-2 py-1">Sell Price</th>
                        <th className="text-left px-2 py-1">Reason</th>
                      </tr>
                    </thead>
                    <tbody>
                      {strategyResult.trades.map((t, idx) => {
                        const isOpen = !t.exit_date || t.exit_reason === 'end_of_data'
                        const buyDate = t.entry_date || (isOpen ? 'pending' : 'Unavailable')
                        const buyPrice = t.entry_price != null ? `₹${Number(t.entry_price).toFixed(2)}` : (isOpen ? 'pending' : 'Unavailable')
                        return (
                          <tr key={idx} className="border-b border-slate-800/20">
                            <td className="px-2 py-1 text-slate-500 font-mono">{idx + 1}</td>
                            <td className="px-2 py-1 text-slate-300">{strategyResult.symbol}</td>
                            <td className="px-2 py-1">
                              <span className="text-emerald-400">Buy</span>
                              <span className="text-slate-500"> → </span>
                              <span className="text-rose-400">Sell</span>
                            </td>
                            <td className="px-2 py-1 text-slate-400 font-mono">{buyDate}</td>
                            <td className={`px-2 py-1 text-right ${t.entry_price != null ? 'text-slate-300' : 'text-slate-500'}`}>{buyPrice}</td>
                            <td className="px-2 py-1 text-slate-400 font-mono">
                              {isOpen ? <span className="text-amber-400">pending</span> : (t.exit_date || 'Unavailable')}
                            </td>
                            <td className="px-2 py-1 text-right">
                              {isOpen
                                ? <span className="text-amber-400">pending</span>
                                : (t.exit_price != null ? `₹${Number(t.exit_price).toFixed(2)}` : 'Unavailable')}
                            </td>
                            <td className="px-2 py-1 text-slate-500">{t.exit_reason || 'open'}</td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="text-slate-500 text-sm py-3">No completed trades in the selected range.</div>
              )}
            </div>
          )}

          {/* Next Trading Session Recommendation — forward-looking, based on latest available candle */}
          {strategyResult?.next_session_recommendation && (
            <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
              <h2 className="text-lg font-semibold text-slate-100 mb-3">Next Trading Session Recommendation</h2>
              {(() => {
                const rec = strategyResult.next_session_recommendation!
                const mh = rec.market_hours
                const isMarketOpen = mh?.market_open
                const nextSession = (() => {
                  const d = new Date(rec.signal_date + 'T00:00:00Z')
                  const next = new Date(d)
                  next.setDate(d.getDate() + 1)
                  while (next.getDay() === 0 || next.getDay() === 6) next.setDate(next.getDate() + 1)
                  return next.toISOString().split('T')[0]
                })()
                // Situation A: market open — a live BUY NOW evaluation. A live intraday
                // signal still executes at the latest verified price, never a fabricated open.
                if (isMarketOpen && rec.has_signal) {
                  const verifiedPrice = liveQuote && liveQuote.price != null ? liveQuote.price : null
                  const priceState = liveQuote?.data_state || 'unavailable'
                  return (
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      <div>
                        <span className="text-slate-400 block text-xs">Live Decision</span>
                        <span className="text-emerald-400 font-semibold">BUY NOW — SIGNAL DETECTED</span>
                      </div>
                      <div>
                        <span className="text-slate-400 block text-xs">Symbol</span>
                        <span className="text-slate-100 font-mono">{rec.symbol}</span>
                      </div>
                      <div>
                        <span className="text-slate-400 block text-xs">Signal Date</span>
                        <span className="text-slate-100 font-mono">{rec.signal_date}</span>
                      </div>
                      <div>
                        <span className="text-slate-400 block text-xs">Suggested Stop-Loss</span>
                        <span className="text-rose-400 font-mono">{rec.stop_loss != null ? `₹${Number(rec.stop_loss).toFixed(2)}` : 'Unavailable'}</span>
                      </div>
                      <div className="col-span-2">
                        <span className="text-slate-400 block text-xs">SMA Condition Satisfied</span>
                        <span className="text-slate-300 text-xs">{rec.action}</span>
                      </div>
                      <div className="col-span-2">
                        <span className="text-slate-400 block text-xs">Exit</span>
                        <span className="text-slate-300 text-xs">{rec.exit_note}</span>
                      </div>
                      <div className="col-span-4">
                        <span className="text-slate-400 block text-xs mb-1">Verified Current Price</span>
                        {verifiedPrice != null ? (
                          <div className="flex items-center gap-3 text-sm">
                            <span className="text-slate-100 font-mono">₹{Number(verifiedPrice).toFixed(2)}</span>
                            <span className={`text-xs ${priceState === 'live' ? 'text-emerald-400' : 'text-amber-400'}`}>
                              {priceState === 'live' ? '● live' : '◐ delayed reference'}
                            </span>
                            {liveQuote?.price_timestamp && (
                              <span className="text-xs text-slate-500">{liveQuote.price_timestamp.replace('T',' ').split('.')[0]} UTC</span>
                            )}
                          </div>
                        ) : (
                          <div className="text-xs text-slate-500">
                            No usable live price from the provider ({priceState}).
                            {liveQuote?.fallback_daily_date ? ` Fallback: last completed daily candle ${liveQuote.fallback_daily_date} (₹ not a live value).` : ''}
                            {' '}Showing the last completed-session decision separately; the live crossover has not been verified.
                          </div>
                        )}
                      </div>
                      <div className="col-span-4 text-xs text-slate-600 border-t border-slate-800 pt-2">
                        {rec.data_freshness} — a live intraday buy, if acted on, executes at the latest verified price; the actual trade entry price is not confirmed until the user's explicit Add action. Stop-loss is a suggested risk-control level, not a guaranteed execution.
                      </div>
                    </div>
                  )
                }
                // Situation B: market closed with a valid signal generated on the latest completed session.
                if (!isMarketOpen && rec.has_signal) {
                  return (
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      <div>
                        <span className="text-slate-400 block text-xs">Recommendation</span>
                        <span className="text-emerald-400 font-semibold">BUY NEXT TRADING SESSION — OPENING PRICE PENDING</span>
                      </div>
                      <div>
                        <span className="text-slate-400 block text-xs">Signal Date</span>
                        <span className="text-slate-100 font-mono">{rec.signal_date}</span>
                      </div>
                      <div>
                        <span className="text-slate-400 block text-xs">Reason</span>
                        <span className="text-slate-300 text-xs">{rec.action || 'Bullish crossover on the latest completed session.'}</span>
                      </div>
                      <div>
                        <span className="text-slate-400 block text-xs">Next Eligible Session</span>
                        <span className="text-slate-100 font-mono">{nextSession}</span>
                      </div>
                      <div>
                        <span className="text-slate-400 block text-xs">Execution Basis</span>
                        <span className="text-amber-400 text-xs">{rec.expected_execution_basis}</span>
                      </div>
                      <div>
                        <span className="text-slate-400 block text-xs">Suggested Stop-Loss</span>
                        <span className="text-rose-400 font-mono">{rec.stop_loss != null ? `₹${Number(rec.stop_loss).toFixed(2)}` : 'Unavailable'}</span>
                      </div>
                      <div className="col-span-4">
                        <span className="text-slate-400 block text-xs">Exit</span>
                        <span className="text-slate-300 text-xs">{rec.exit_note}</span>
                      </div>
                      <div className="col-span-4 text-xs text-slate-600 border-t border-slate-800 pt-2">
                        The actual opening price for {nextSession} is not yet known and is not invented here.
                        {rec.data_freshness ? ` · ${rec.data_freshness}` : ''} — based on latest available data only.
                      </div>
                    </div>
                  )
                }
                // Situation C: no valid buy signal.
                return (
                  <div className="py-1">
                    <div className="flex items-center gap-3 py-2 flex-wrap">
                      <span className="bg-slate-800 border border-slate-700 text-slate-300 px-3 py-2 rounded-md text-sm">
                        NO NEW BUY SIGNAL
                      </span>
                      <span className="text-xs text-slate-500">{rec.reason || 'No bullish crossover was detected on the latest evaluated data.'}</span>
                      <span className="text-xs text-slate-600 ml-auto">{rec.data_freshness}</span>
                    </div>
                    {!isMarketOpen && mh && (
                      <div className="text-xs text-slate-600 mt-2">
                        Market is closed ({mh.session_open}–{mh.session_close} {mh.timezone}). This decision is based on the latest completed session only; a next-session recommendation will not be shown unless a valid signal exists.
                      </div>
                    )}
                  </div>
                )
              })()}
            </div>
          )}

          {/* Bottom: Strategy Results & Active Positions */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Left: Historical Strategy Table */}
            <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
              <h2 className="text-lg font-semibold text-slate-100 mb-4">Trade History</h2>
              {trades.length > 0 ? (
                <div className="overflow-x-auto max-h-64">
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
                          <td className="px-2 py-1 text-slate-400 font-mono">{trade.entry_date || 'Unavailable'}</td>
                          <td className="px-2 py-1 text-right text-slate-300">{trade.entry_price != null ? `₹${Number(trade.entry_price).toFixed(2)}` : 'Unavailable'}</td>
                          <td className="px-2 py-1 text-slate-400 font-mono">{trade.exit_date || 'Unavailable'}</td>
                          <td className={`px-2 py-1 text-right font-medium ${trade.net_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                            {trade.net_pnl >= 0 ? '+' : ''}{trade.net_pnl.toFixed(1)}%
                          </td>
                          <td className="px-2 py-1 text-slate-500">{trade.exit_reason}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="text-slate-500 text-sm py-4 text-center">No closed trades yet. Run a strategy to see results.</div>
              )}
            </div>

            {/* Right: Active Positions */}
            <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
              <h2 className="text-lg font-semibold text-slate-100 mb-4">Active Positions</h2>
              {positions.length > 0 ? (
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
              ) : (
                <div className="text-slate-500 text-sm py-4 text-center">No active positions. Run a strategy and add a position to see it here.</div>
              )}
            </div>
          </div>
      </div>

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
                  <span className="text-slate-200 ml-2 font-mono">{selectedTrade.entry_date || 'Unavailable'}</span>
                </div>
                <div>
                  <span className="text-slate-400">Entry Price:</span>
                  <span className="text-slate-200 ml-2">{selectedTrade.entry_price != null ? `₹${Number(selectedTrade.entry_price).toFixed(2)}` : 'Unavailable'}</span>
                </div>
                <div>
                  <span className="text-slate-400">Exit Date:</span>
                  <span className="text-slate-200 ml-2 font-mono">{selectedTrade.exit_date || 'Unavailable'}</span>
                </div>
                <div>
                  <span className="text-slate-400">Exit Price:</span>
                  <span className="text-slate-200 ml-2">{selectedTrade.exit_price != null ? `₹${Number(selectedTrade.exit_price).toFixed(2)}` : 'Unavailable'}</span>
                </div>
                <div>
                  <span className="text-slate-400">Stop Price:</span>
                  <span className="text-rose-400 ml-2">{selectedTrade.stop_price != null ? `₹${Number(selectedTrade.stop_price).toFixed(2)}` : 'Unavailable'}</span>
                </div>
                <div>
                  <span className="text-slate-400">Exit Reason:</span>
                  <span className="text-slate-200 ml-2">{selectedTrade.exit_reason || 'Unavailable'}</span>
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
