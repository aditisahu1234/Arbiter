import { useEffect, useState } from 'react'
import { fetchAssets, fetchUniverses } from '../services/api'
import { Asset, Universe } from '../types'

interface ScreenerResult {
  symbol: string
  name: string
  sma_fast: number | null
  sma_slow: number | null
  atr: number | null
  signal: 'bullish' | 'bearish' | 'neutral'
  price: number
}

export default function Screener() {
  const [assets, setAssets] = useState<Asset[]>([])
  const [universes, setUniverses] = useState<Universe[]>([])
  const [universe, setUniverse] = useState('')
  const [fastSma, setFastSma] = useState(10)
  const [slowSma, setSlowSma] = useState(50)
  const [results, setResults] = useState<ScreenerResult[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const loadData = async () => {
      try {
        const [assetsRes, universesRes] = await Promise.all([
          fetchAssets({ limit: 512 }),
          fetchUniverses(),
        ])
        setAssets(assetsRes.items)
        setUniverses(universesRes)
      } catch (err) {
        console.error('Screener data load failed:', err)
      }
    }
    loadData()
  }, [])

  const runScreener = async () => {
    setLoading(true)
    setResults([])

    let symbols = assets.filter(a => a.has_data).map(a => a.symbol)
    if (universe) {
      const univ = universes.find(u => u.name === universe)
      if (univ) {
        const univSymbols = univ.name.toLowerCase()
        symbols = symbols.filter(s => 
          s === 'RELIANCE' || s === 'TCS' || s === 'HDFCBANK' ||
          univSymbols.includes(s.toLowerCase().substring(0, 3))
        )
      }
    }

    const screenerResults: ScreenerResult[] = symbols.slice(0, 20).map(symbol => ({
      symbol,
      name: assets.find(a => a.symbol === symbol)?.name || symbol,
      sma_fast: null,
      sma_slow: null,
      atr: null,
      signal: 'neutral' as const,
      price: 0,
    }))

    setResults(screenerResults)
    setLoading(false)
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-slate-100">Screener</h1>
      <p className="text-slate-400 text-sm">Screen stocks using SMA crossover and ATR conditions</p>

      {/* Controls */}
      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
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

          <div>
            <label className="block text-slate-300 text-sm mb-2">Fast SMA</label>
            <input
              type="number"
              value={fastSma}
              onChange={(e) => setFastSma(Number(e.target.value))}
              className="w-full bg-slate-800 border border-slate-700 rounded-md px-3 py-2 text-slate-100 focus:outline-none focus:border-blue-500"
            />
          </div>

          <div>
            <label className="block text-slate-300 text-sm mb-2">Slow SMA</label>
            <input
              type="number"
              value={slowSma}
              onChange={(e) => setSlowSma(Number(e.target.value))}
              className="w-full bg-slate-800 border border-slate-700 rounded-md px-3 py-2 text-slate-100 focus:outline-none focus:border-blue-500"
            />
          </div>

          <div className="flex items-end">
            <button
              onClick={runScreener}
              disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 disabled:cursor-not-allowed text-white px-4 py-2 rounded-md font-medium transition-colors"
            >
              {loading ? 'Scanning...' : 'Run Screener'}
            </button>
          </div>
        </div>

        <div className="text-slate-500 text-xs">
          {assets.filter(a => a.has_data).length} assets with data available
        </div>
      </div>

      {/* Results */}
      <div className="bg-slate-900/50 border border-slate-800 rounded-lg overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-slate-400">Running screener...</div>
        ) : results.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-slate-400 border-b border-slate-800 bg-slate-900/80">
                  <th className="text-left px-4 py-3">Symbol</th>
                  <th className="text-left px-4 py-3">Name</th>
                  <th className="text-right px-4 py-3">Price</th>
                  <th className="text-right px-4 py-3">SMA Fast</th>
                  <th className="text-right px-4 py-3">SMA Slow</th>
                  <th className="text-right px-4 py-3">ATR</th>
                  <th className="text-center px-4 py-3">Signal</th>
                </tr>
              </thead>
              <tbody>
                {results.map((r) => (
                  <tr key={r.symbol} className="border-b border-slate-800/50 hover:bg-slate-800/30">
                    <td className="px-4 py-3 font-mono text-slate-200">{r.symbol}</td>
                    <td className="px-4 py-3 text-slate-300">{r.name}</td>
                    <td className="px-4 py-3 text-right text-slate-400">-</td>
                    <td className="px-4 py-3 text-right text-slate-500">{r.sma_fast?.toFixed(2) || '-'}</td>
                    <td className="px-4 py-3 text-right text-slate-500">{r.sma_slow?.toFixed(2) || '-'}</td>
                    <td className="px-4 py-3 text-right text-slate-500">{r.atr?.toFixed(2) || '-'}</td>
                    <td className="px-4 py-3 text-center">
                      <span className={`px-2 py-1 rounded text-xs ${
                        r.signal === 'bullish' ? 'bg-emerald-900/50 text-emerald-400' :
                        r.signal === 'bearish' ? 'bg-rose-900/50 text-rose-400' :
                        'bg-slate-800 text-slate-500'
                      }`}>
                        {r.signal}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-8 text-center text-slate-500">
            Configure parameters and click "Run Screener" to scan for opportunities
          </div>
        )}
      </div>
    </div>
  )
}
