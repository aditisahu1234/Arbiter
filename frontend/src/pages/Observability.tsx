import { useEffect, useState } from 'react'
import { fetchLakehouseStatus, fetchHealth } from '../services/api'

export default function Observability() {
  const [lakehouse, setLakehouse] = useState<any>(null)
  const [health, setHealth] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const loadData = async () => {
      try {
        const [lake, h] = await Promise.all([
          fetchLakehouseStatus(),
          fetchHealth(),
        ])
        setLakehouse(lake)
        setHealth(h)
      } catch (err) {
        console.error('Observability data load failed:', err)
      } finally {
        setLoading(false)
      }
    }
    loadData()
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-slate-400">Loading observability data...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-slate-100">Observability</h1>

      {/* System Status */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
          <h2 className="text-lg font-semibold text-slate-100 mb-4">System Health</h2>
          <div className="space-y-2">
            <div className="flex justify-between">
              <span className="text-slate-400">Service</span>
              <span className="text-emerald-400">{health?.service || 'Arbiter'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Status</span>
              <span className="text-emerald-400">{health?.status || 'ok'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Environment</span>
              <span className="text-slate-200">{health?.environment || 'development'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Version</span>
              <span className="text-slate-200">{health?.version || '0.1.0'}</span>
            </div>
          </div>
        </div>

        <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
          <h2 className="text-lg font-semibold text-slate-100 mb-4">Data Coverage</h2>
          <div className="space-y-2">
            <div className="flex justify-between">
              <span className="text-slate-400">Parquet Files</span>
              <span className="text-blue-400">{lakehouse?.total_files || 0}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Total Bars</span>
              <span className="text-blue-400">{lakehouse?.total_bars_ingested?.toLocaleString() || 0}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Data Size</span>
              <span className="text-blue-400">{lakehouse?.total_size_mb?.toFixed(2) || 0} MB</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Latest Date</span>
              <span className="text-slate-200">{lakehouse?.latest_date || 'N/A'}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Asset Coverage */}
      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
        <h2 className="text-lg font-semibold text-slate-100 mb-4">Asset Coverage</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {lakehouse?.assets?.slice(0, 12).map((asset: any) => (
            <div key={asset.symbol} className="bg-slate-800/50 rounded p-3">
              <div className="text-slate-200 font-mono text-sm">{asset.symbol}</div>
              <div className="text-slate-500 text-xs mt-1">
                {asset.rows} bars
              </div>
              <div className="text-slate-600 text-xs">
                {asset.latest_date}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Metrics Endpoint */}
      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
        <h2 className="text-lg font-semibold text-slate-100 mb-4">Prometheus Metrics</h2>
        <div className="text-slate-400 text-sm">
          <p className="mb-2">Access metrics at: <code className="text-blue-400">http://localhost:8000/metrics</code></p>
          <p className="text-slate-500">
            Metrics include: request counts, latency, ingestion stats, data coverage
          </p>
        </div>
      </div>
    </div>
  )
}
