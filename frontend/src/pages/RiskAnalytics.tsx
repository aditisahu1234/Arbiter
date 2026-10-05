import { useEffect, useState } from 'react'
import { fetchAssets, runCAPM, runFF3 } from '../services/api'
import { Asset } from '../types'

interface CAPMResult {
  symbol: string
  alpha: number
  beta: number
  r_squared: number
  risk_free_source: string
  observations: number
}

interface FF3Result {
  symbol: string
  alpha: number
  beta_market: number
  beta_size: number
  beta_value: number
  r_squared: number
  factor_source: string
  is_production_factor: boolean
}

export default function RiskAnalytics() {
  const [assets, setAssets] = useState<Asset[]>([])
  const [selectedSymbol, setSelectedSymbol] = useState('TCS')
  const [capmResult, setCapmResult] = useState<CAPMResult | null>(null)
  const [ff3Result, setFf3Result] = useState<FF3Result | null>(null)
  const [loading, setLoading] = useState(false)
  const [ff3Source, setFf3Source] = useState('synthetic')

  useEffect(() => {
    const loadData = async () => {
      try {
        const res = await fetchAssets({ limit: 100 })
        setAssets(res.items)
      } catch (err) {
        console.error('Risk Analytics data load failed:', err)
      }
    }
    loadData()
  }, [])

  const runAnalysis = async () => {
    setLoading(true)
    try {
      const [capmRes, ff3Res] = await Promise.all([
        runCAPM({ symbol: selectedSymbol }),
        runFF3({ symbol: selectedSymbol, factor_source: ff3Source }),
      ])
      setCapmResult(capmRes)
      setFf3Result(ff3Res)
    } catch (err) {
      console.error('Analysis failed:', err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-slate-100">Risk Analytics</h1>
      <p className="text-slate-400 text-sm">CAPM and Fama-French factor analysis</p>

      {/* Controls */}
      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4 flex gap-4 items-end flex-wrap">
        <div>
          <label className="block text-slate-300 text-sm mb-2">Asset</label>
          <select
            value={selectedSymbol}
            onChange={(e) => setSelectedSymbol(e.target.value)}
            className="bg-slate-800 border border-slate-700 rounded-md px-3 py-2 text-slate-100 focus:outline-none focus:border-blue-500"
          >
            {assets.map((a) => (
              <option key={a.symbol} value={a.symbol}>{a.symbol}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-slate-300 text-sm mb-2">FF3 Factor Source</label>
          <select
            value={ff3Source}
            onChange={(e) => setFf3Source(e.target.value)}
            className="bg-slate-800 border border-slate-700 rounded-md px-3 py-2 text-slate-100 focus:outline-none focus:border-blue-500"
          >
            <option value="synthetic">Synthetic (auto-generated)</option>
            <option value="iim_ahmedabad">IIM Ahmedabad (production)</option>
          </select>
        </div>

        <button
          onClick={runAnalysis}
          disabled={loading}
          className="bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 disabled:cursor-not-allowed text-white px-4 py-2 rounded-md font-medium transition-colors"
        >
          {loading ? 'Analyzing...' : 'Run Analysis'}
        </button>
      </div>

      {/* CAPM Results */}
      {capmResult && (
        <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
          <h2 className="text-lg font-semibold text-slate-100 mb-4">CAPM Analysis</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <div className="text-slate-400 text-xs">Alpha</div>
              <div className={`text-xl font-bold ${capmResult.alpha >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                {capmResult.alpha.toFixed(4)}%
              </div>
            </div>
            <div>
              <div className="text-slate-400 text-xs">Beta</div>
              <div className="text-xl font-bold text-slate-100">
                {capmResult.beta.toFixed(4)}
              </div>
            </div>
            <div>
              <div className="text-slate-400 text-xs">R²</div>
              <div className="text-xl font-bold text-slate-100">
                {capmResult.r_squared.toFixed(4)}
              </div>
            </div>
            <div>
              <div className="text-slate-400 text-xs">Observations</div>
              <div className="text-xl font-bold text-slate-100">
                {capmResult.observations}
              </div>
            </div>
          </div>
          <div className="mt-4 text-xs text-slate-500">
            Risk-free source: {capmResult.risk_free_source}
          </div>
        </div>
      )}

      {/* FF3 Results */}
      {ff3Result && (
        <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
          <h2 className="text-lg font-semibold text-slate-100 mb-4">Fama-French 3-Factor</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <div className="text-slate-400 text-xs">Alpha</div>
              <div className={`text-xl font-bold ${ff3Result.alpha >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                {ff3Result.alpha.toFixed(4)}%
              </div>
            </div>
            <div>
              <div className="text-slate-400 text-xs">Market Beta</div>
              <div className="text-xl font-bold text-slate-100">
                {ff3Result.beta_market.toFixed(4)}
              </div>
            </div>
            <div>
              <div className="text-slate-400 text-xs">Size Beta (SMB)</div>
              <div className="text-xl font-bold text-slate-100">
                {ff3Result.beta_size.toFixed(4)}
              </div>
            </div>
            <div>
              <div className="text-slate-400 text-xs">Value Beta (HML)</div>
              <div className="text-xl font-bold text-slate-100">
                {ff3Result.beta_value.toFixed(4)}
              </div>
            </div>
            <div>
              <div className="text-slate-400 text-xs">R²</div>
              <div className="text-xl font-bold text-slate-100">
                {ff3Result.r_squared.toFixed(4)}
              </div>
            </div>
            <div>
              <div className="text-slate-400 text-xs">Factor Source</div>
              <div className="text-sm font-medium text-slate-200">
                {ff3Result.factor_source}
              </div>
              <div className="text-xs text-slate-500">
                {ff3Result.is_production_factor ? '✓ Production' : '○ Synthetic'}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Explanation */}
      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
        <h3 className="text-slate-200 font-medium mb-2">Understanding the Metrics</h3>
        <div className="space-y-2 text-sm text-slate-400">
          <p><strong className="text-slate-300">Alpha:</strong> Excess return above what the model predicts. Positive alpha indicates outperformance.</p>
          <p><strong className="text-slate-300">Beta:</strong> Sensitivity to market movements. Beta &gt; 1 means more volatile than market.</p>
          <p><strong className="text-slate-300">R²:</strong> How much of the stock's movement is explained by the factors. Closer to 1 is better fit.</p>
          {ff3Source === 'synthetic' && (
            <p className="text-amber-400">
              Note: Using synthetic factors (based on sector comparisons). For production-quality analysis, select "IIM Ahmedabad" and ensure the factor data file is available.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
