import { useEffect, useState } from 'react'
import { fetchLakehouseStatus, fetchUniverses, fetchAssets } from '../services/api'
import { LakehouseStatus, Universe, Asset } from '../types'

export default function Dashboard() {
  const [lakehouse, setLakehouse] = useState<LakehouseStatus | null>(null)
  const [universes, setUniverses] = useState<Universe[]>([])
  const [assets, setAssets] = useState<Asset[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const loadData = async () => {
      try {
        const [lake, univ, assetRes] = await Promise.all([
          fetchLakehouseStatus(),
          fetchUniverses(),
          fetchAssets({ limit: 5 }),
        ])
        setLakehouse(lake)
        setUniverses(univ)
        setAssets(assetRes.items)
      } catch (err) {
        console.error('Dashboard data load failed:', err)
      } finally {
        setLoading(false)
      }
    }
    loadData()
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-slate-400">Loading dashboard...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-slate-100">Dashboard</h1>

      {/* Market Overview */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
          <div className="text-slate-400 text-sm">Total Assets</div>
          <div className="text-3xl font-bold text-slate-100 mt-1">512</div>
          <div className="text-emerald-400 text-xs mt-1">Seeded in database</div>
        </div>

        <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
          <div className="text-slate-400 text-sm">Populated Assets</div>
          <div className="text-3xl font-bold text-emerald-400 mt-1">
            {lakehouse?.total_files || 0}
          </div>
          <div className="text-slate-400 text-xs mt-1">
            {lakehouse ? `${((lakehouse.total_files / 512) * 100).toFixed(1)}% coverage` : ''}
          </div>
        </div>

        <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
          <div className="text-slate-400 text-sm">Total Bars</div>
          <div className="text-3xl font-bold text-blue-400 mt-1">
            {lakehouse?.total_bars_ingested ? (lakehouse.total_bars_ingested / 1000).toFixed(1) + 'k' : '0'}
          </div>
          <div className="text-slate-400 text-xs mt-1">OHLCV records</div>
        </div>

        <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
          <div className="text-slate-400 text-sm">Universes</div>
          <div className="text-3xl font-bold text-purple-400 mt-1">
            {universes.length}
          </div>
          <div className="text-slate-400 text-xs mt-1">Active portfolios</div>
        </div>
      </div>

      {/* Universe Summary */}
      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
        <h2 className="text-lg font-semibold text-slate-100 mb-4">Universe Coverage</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {universes.map((u) => (
            <div key={u.id} className="bg-slate-800/50 rounded p-3">
              <div className="text-slate-300 font-medium">{u.display_name}</div>
              <div className="text-slate-500 text-sm">{u.member_count} assets</div>
            </div>
          ))}
        </div>
      </div>

      {/* Latest Data */}
      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
        <h2 className="text-lg font-semibold text-slate-100 mb-4">Latest Market Data</h2>
        <div className="text-slate-400 text-sm">
          {lakehouse?.latest_date ? (
            <div>
              <div className="text-slate-200">Last updated: {lakehouse.latest_date}</div>
              <div className="text-slate-500 mt-1">
                {lakehouse.assets?.length || 0} assets with data
              </div>
            </div>
          ) : (
            <div>No data available</div>
          )}
        </div>
      </div>

      {/* Top Assets by Data */}
      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
        <h2 className="text-lg font-semibold text-slate-100 mb-4">Recent Assets</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-slate-400 border-b border-slate-800">
                <th className="text-left pb-2">Symbol</th>
                <th className="text-left pb-2">Name</th>
                <th className="text-left pb-2">Sector</th>
                <th className="text-right pb-2">Bars</th>
              </tr>
            </thead>
            <tbody>
              {assets.slice(0, 5).map((asset) => (
                <tr key={asset.symbol} className="border-b border-slate-800/50">
                  <td className="py-2 text-slate-200 font-mono">{asset.symbol}</td>
                  <td className="py-2 text-slate-400">{asset.name}</td>
                  <td className="py-2 text-slate-500">{asset.sector}</td>
                  <td className="py-2 text-right text-slate-400">{asset.has_data ? '✓' : '○'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
