import { useState, useEffect } from 'react'
import { fetchAssets, fetchUniverses, runBacktest } from '../services/api'
import { Asset, Universe } from '../types'
import { StrategyParams } from '../types/backtest'

export default function StrategyLab() {
  // Navigation handled by direct URL change
  const [_assets, setAssets] = useState<Asset[]>([])
  const [universes, setUniverses] = useState<Universe[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Form state
  const [symbol, setSymbol] = useState('TCS')
  const [universe, setUniverse] = useState('')
  const [fastSma, setFastSma] = useState(10)
  const [slowSma, setSlowSma] = useState(50)
  const [atrWindow, setAtrWindow] = useState(14)
  const [atrMultiplier, setAtrMultiplier] = useState(2.0)
  const [costBps, setCostBps] = useState(10)
  const [startDate, setStartDate] = useState('2021-10-01')
  const [endDate, setEndDate] = useState('2026-10-01')

  // Validation errors
  const [errors, setErrors] = useState<Record<string, string>>({})

  useEffect(() => {
    const loadData = async () => {
      try {
        const [assetsRes, universesRes] = await Promise.all([
          fetchAssets({ limit: 100 }),
          fetchUniverses(),
        ])
        setAssets(assetsRes.items)
        setUniverses(universesRes)
      } catch (err) {
        console.error('Failed to load data:', err)
      }
    }
    loadData()
  }, [])

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {}

    if (!symbol) newErrors.symbol = 'Symbol is required'
    if (fastSma <= 0) newErrors.fastSma = 'Fast SMA must be > 0'
    if (slowSma <= 0) newErrors.slowSma = 'Slow SMA must be > 0'
    if (fastSma >= slowSma) newErrors.slowSma = 'Slow SMA must be > Fast SMA'
    if (atrWindow < 2) newErrors.atrWindow = 'ATR window must be >= 2'
    if (atrMultiplier <= 0) newErrors.atrMultiplier = 'ATR multiplier must be > 0'
    if (costBps < 0) newErrors.costBps = 'Cost must be >= 0'
    if (startDate >= endDate) newErrors.dateRange = 'Start date must be before end date'

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleRunBacktest = async () => {
    if (!validate()) return

    setLoading(true)
    setError(null)

    try {
      const params: StrategyParams = {
        symbol,
        universe: universe || undefined,
        fast_sma: fastSma,
        slow_sma: slowSma,
        atr_window: atrWindow,
        atr_multiplier: atrMultiplier,
        transaction_cost_bps: costBps,
        start_date: startDate,
        end_date: endDate,
      }

      const result = await runBacktest(params)
      
      // Store result in localStorage and navigate
      localStorage.setItem('lastBacktestResult', JSON.stringify({ result, params }))
      window.location.href = '/results'
    } catch (err: any) {
      setError(err.message || 'Backtest failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <h1 className="text-2xl font-semibold text-slate-100">Strategy Lab</h1>
      <p className="text-slate-400 text-sm">Configure SMA Crossover + ATR Stop-Loss strategy parameters</p>

      {error && (
        <div className="bg-rose-950/50 border border-rose-800 text-rose-200 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6 space-y-6">
        {/* Asset Selection */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-slate-300 text-sm mb-2">Asset Symbol</label>
            <input
              type="text"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.toUpperCase())}
              className="w-full bg-slate-800 border border-slate-700 rounded-md px-3 py-2 text-slate-100 font-mono focus:outline-none focus:border-blue-500"
              placeholder="e.g. TCS, RELIANCE"
            />
            {errors.symbol && <p className="text-rose-400 text-xs mt-1">{errors.symbol}</p>}
          </div>

          <div>
            <label className="block text-slate-300 text-sm mb-2">Universe</label>
            <select
              value={universe}
              onChange={(e) => setUniverse(e.target.value)}
              className="w-full bg-slate-800 border border-slate-700 rounded-md px-3 py-2 text-slate-100 focus:outline-none focus:border-blue-500"
            >
              <option value="">All Assets</option>
              {universes.map((u) => (
                <option key={u.name} value={u.name}>{u.display_name}</option>
              ))}
            </select>
          </div>
        </div>

        {/* SMA Parameters */}
        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="block text-slate-300 text-sm mb-2">Fast SMA</label>
            <input
              type="number"
              value={fastSma}
              onChange={(e) => setFastSma(Number(e.target.value))}
              className="w-full bg-slate-800 border border-slate-700 rounded-md px-3 py-2 text-slate-100 focus:outline-none focus:border-blue-500"
            />
            {errors.fastSma && <p className="text-rose-400 text-xs mt-1">{errors.fastSma}</p>}
          </div>

          <div>
            <label className="block text-slate-300 text-sm mb-2">Slow SMA</label>
            <input
              type="number"
              value={slowSma}
              onChange={(e) => setSlowSma(Number(e.target.value))}
              className="w-full bg-slate-800 border border-slate-700 rounded-md px-3 py-2 text-slate-100 focus:outline-none focus:border-blue-500"
            />
            {errors.slowSma && <p className="text-rose-400 text-xs mt-1">{errors.slowSma}</p>}
          </div>

          <div>
            <label className="block text-slate-300 text-sm mb-2">ATR Window</label>
            <input
              type="number"
              value={atrWindow}
              onChange={(e) => setAtrWindow(Number(e.target.value))}
              className="w-full bg-slate-800 border border-slate-700 rounded-md px-3 py-2 text-slate-100 focus:outline-none focus:border-blue-500"
            />
            {errors.atrWindow && <p className="text-rose-400 text-xs mt-1">{errors.atrWindow}</p>}
          </div>
        </div>

        {/* ATR & Cost Parameters */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-slate-300 text-sm mb-2">ATR Multiplier</label>
            <input
              type="number"
              step="0.1"
              value={atrMultiplier}
              onChange={(e) => setAtrMultiplier(Number(e.target.value))}
              className="w-full bg-slate-800 border border-slate-700 rounded-md px-3 py-2 text-slate-100 focus:outline-none focus:border-blue-500"
            />
            {errors.atrMultiplier && <p className="text-rose-400 text-xs mt-1">{errors.atrMultiplier}</p>}
          </div>

          <div>
            <label className="block text-slate-300 text-sm mb-2">Transaction Cost (bps)</label>
            <input
              type="number"
              value={costBps}
              onChange={(e) => setCostBps(Number(e.target.value))}
              className="w-full bg-slate-800 border border-slate-700 rounded-md px-3 py-2 text-slate-100 focus:outline-none focus:border-blue-500"
            />
            {errors.costBps && <p className="text-rose-400 text-xs mt-1">{errors.costBps}</p>}
          </div>
        </div>

        {/* Date Range */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-slate-300 text-sm mb-2">Start Date</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-full bg-slate-800 border border-slate-700 rounded-md px-3 py-2 text-slate-100 focus:outline-none focus:border-blue-500"
            />
            {errors.dateRange && <p className="text-rose-400 text-xs mt-1">{errors.dateRange}</p>}
          </div>

          <div>
            <label className="block text-slate-300 text-sm mb-2">End Date</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="w-full bg-slate-800 border border-slate-700 rounded-md px-3 py-2 text-slate-100 focus:outline-none focus:border-blue-500"
            />
          </div>
        </div>

        {/* Run Button */}
        <div className="flex justify-end">
          <button
            onClick={handleRunBacktest}
            disabled={loading}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 disabled:cursor-not-allowed text-white px-6 py-2 rounded-md font-medium transition-colors"
          >
            {loading ? 'Running...' : 'Run Backtest'}
          </button>
        </div>
      </div>

      {/* Strategy Description */}
      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
        <h3 className="text-slate-200 font-medium mb-2">Strategy: SMA Crossover + ATR Stop-Loss</h3>
        <ul className="text-slate-400 text-sm space-y-1">
          <li>• Entry: Fast SMA crosses above Slow SMA</li>
          <li>• Exit: Fast SMA crosses below Slow SMA</li>
          <li>• Stop-Loss: {atrMultiplier}x ATR below entry price</li>
          <li>• Execution: Next-bar open (prevents look-ahead bias)</li>
          <li>• Transaction Cost: {costBps} bps round-trip</li>
        </ul>
      </div>
    </div>
  )
}
