import { useEffect, useState } from 'react'
import { fetchAssets, runCAPM, runFF3 } from '../services/api'
import { Asset } from '../types'

export default function CAPMFF3() {
  const [assets, setAssets] = useState<Asset[]>([])
  const [selectedSymbol, setSelectedSymbol] = useState('TCS')
  const [capmResult, setCapmResult] = useState<any>(null)
  const [ff3Result, setFf3Result] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [ff3Source, setFf3Source] = useState('synthetic')

  useEffect(() => {
    const loadData = async () => {
      try {
        const res = await fetchAssets({ limit: 100 })
        setAssets(res.items)
      } catch (err) {
        console.error('Failed to load assets:', err)
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
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-semibold text-slate-100">CAPM & Fama-French</h1>
          <p className="text-slate-400 text-sm mt-1">Risk-adjusted performance analysis</p>
        </div>
      </div>

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
            <option value="synthetic">Synthetic (default)</option>
            <option value="iim_ahmedabad">IIM Ahmedabad (production)</option>
          </select>
        </div>

        <button
          onClick={runAnalysis}
          disabled={loading}
          className="bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 disabled:cursor-not-allowed text-white px-6 py-2 rounded-md font-medium transition-colors"
        >
          {loading ? 'Analyzing...' : 'Run Analysis'}
        </button>
      </div>

      {/* CAPM Results */}
      {capmResult && (
        <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
          <h2 className="text-lg font-semibold text-slate-100 mb-4 flex items-center gap-2">
            CAPM Analysis
            <span className="text-xs font-normal text-slate-500">
              ({capmResult.risk_free_source})
            </span>
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div className="bg-slate-800/50 rounded p-3">
              <div className="text-slate-400 text-xs">Alpha</div>
              <div className={`text-lg font-bold ${capmResult.alpha >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                {capmResult.alpha.toFixed(4)}%
              </div>
              <div className="text-slate-600 text-xs mt-1">Annualized excess return</div>
            </div>
            <div className="bg-slate-800/50 rounded p-3">
              <div className="text-slate-400 text-xs">Beta</div>
              <div className="text-lg font-bold text-slate-100">
                {capmResult.beta.toFixed(4)}
              </div>
              <div className="text-slate-600 text-xs mt-1">Market sensitivity</div>
            </div>
            <div className="bg-slate-800/50 rounded p-3">
              <div className="text-slate-400 text-xs">R²</div>
              <div className="text-lg font-bold text-slate-100">
                {capmResult.r_squared.toFixed(4)}
              </div>
              <div className="text-slate-600 text-xs mt-1">Model fit</div>
            </div>
            <div className="bg-slate-800/50 rounded p-3">
              <div className="text-slate-400 text-xs">Risk-free Rate</div>
              <div className="text-lg font-bold text-slate-100">
                {capmResult.risk_free_annual_pct.toFixed(2)}%
              </div>
              <div className="text-slate-600 text-xs mt-1">Annual</div>
            </div>
            <div className="bg-slate-800/50 rounded p-3">
              <div className="text-slate-400 text-xs">Observations</div>
              <div className="text-lg font-bold text-slate-100">
                {capmResult.observations}
              </div>
              <div className="text-slate-600 text-xs mt-1">Trading days</div>
            </div>
          </div>
          {capmResult.alpha_p_value !== undefined && (
            <div className="mt-4 text-xs text-slate-500">
              Alpha t-stat: {capmResult.alpha_t_stat.toFixed(2)} | 
              p-value: {capmResult.alpha_p_value.toFixed(4)}
              {capmResult.risk_free_source_production ? '' : ' ⚠️ Non-production risk-free rate source'}
            </div>
          )}
        </div>
      )}

      {/* FF3 Results */}
      {ff3Result && (
        <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
          <h2 className="text-lg font-semibold text-slate-100 mb-4 flex items-center gap-2">
            Fama-French 3-Factor
            <span className={`text-xs font-normal px-2 py-0.5 rounded ${
              ff3Result.is_production_factor 
                ? 'bg-emerald-900/50 text-emerald-400' 
                : 'bg-amber-900/50 text-amber-400'
            }`}>
              {ff3Result.is_production_factor ? 'Production' : 'Synthetic'}
            </span>
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div className="bg-slate-800/50 rounded p-3">
              <div className="text-slate-400 text-xs">Alpha</div>
              <div className={`text-lg font-bold ${ff3Result.alpha >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                {ff3Result.alpha.toFixed(4)}%
              </div>
              <div className="text-slate-600 text-xs mt-1">Three-factor excess</div>
            </div>
            <div className="bg-slate-800/50 rounded p-3">
              <div className="text-slate-400 text-xs">Market Beta</div>
              <div className="text-lg font-bold text-slate-100">
                {ff3Result.beta_market.toFixed(4)}
              </div>
              <div className="text-slate-600 text-xs mt-1">Mkt-RF factor</div>
            </div>
            <div className="bg-slate-800/50 rounded p-3">
              <div className="text-slate-400 text-xs">Size Beta</div>
              <div className="text-lg font-bold text-slate-100">
                {ff3Result.beta_size.toFixed(4)}
              </div>
              <div className="text-slate-600 text-xs mt-1">SMB factor</div>
            </div>
            <div className="bg-slate-800/50 rounded p-3">
              <div className="text-slate-400 text-xs">Value Beta</div>
              <div className="text-lg font-bold text-slate-100">
                {ff3Result.beta_value.toFixed(4)}
              </div>
              <div className="text-slate-600 text-xs mt-1">HML factor</div>
            </div>
            <div className="bg-slate-800/50 rounded p-3">
              <div className="text-slate-400 text-xs">R²</div>
              <div className="text-lg font-bold text-slate-100">
                {ff3Result.r_squared.toFixed(4)}
              </div>
              <div className="text-slate-600 text-xs mt-1">Model fit</div>
            </div>
          </div>
          <div className="mt-4 text-xs text-slate-500">
            Factor source: {ff3Result.factor_provenance} ({ff3Result.factor_frequency})
            {ff3Result.alpha_p_value !== undefined && (
              <span className="ml-4">
                | t-stat: {ff3Result.alpha_t_stat.toFixed(2)} | p-value: {ff3Result.alpha_p_value.toFixed(4)}
              </span>
            )}
          </div>
        </div>
      )}

      {/* Info */}
      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
        <h3 className="text-slate-200 font-medium mb-3">About These Models</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-sm text-slate-400">
          <div>
            <p className="text-slate-300 font-medium mb-1">CAPM (Capital Asset Pricing Model)</p>
            <p>Measures expected return based on systematic risk (beta). Alpha represents excess return not explained by market risk.</p>
            <div className="mt-2 text-xs text-slate-500">
              Uses {capmResult?.risk_free_source || 'RBI fallback'} risk-free rate
            </div>
          </div>
          <div>
            <p className="text-slate-300 font-medium mb-1">Fama-French 3-Factor</p>
            <p>Extends CAPM with size (SMB) and value (HML) factors. Better explains cross-sectional returns.</p>
            <div className="mt-2 text-xs">
              {ff3Result?.is_production_factor 
                ? <span className="text-emerald-400">✓ Using IIM Ahmedabad production factors</span>
                : <span className="text-amber-400">○ Using synthetic factors (sector-based)</span>
              }
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
