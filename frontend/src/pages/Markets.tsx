import { useEffect, useState } from 'react'
import { fetchAssets, fetchLakehouseStatus } from '../services/api'
import { Asset, LakehouseStatus } from '../types'

export default function Markets() {
  const [assets, setAssets] = useState<Asset[]>([])
  const [lakehouse, setLakehouse] = useState<LakehouseStatus | null>(null)
  const [filter, setFilter] = useState('')
  const [sectorFilter, setSectorFilter] = useState('')
  const [showOnlyAvailable, setShowOnlyAvailable] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const loadData = async () => {
      setLoading(true)
      try {
        const [assetsRes, lake] = await Promise.all([
          fetchAssets({ limit: 512 }),
          fetchLakehouseStatus(),
        ])
        setAssets(assetsRes.items)
        setLakehouse(lake)
      } catch (err) {
        console.error('Markets data load failed:', err)
      } finally {
        setLoading(false)
      }
    }
    loadData()
  }, [])

  const sectors = [...new Set(assets.map(a => a.sector).filter((s): s is string => Boolean(s)))]

  const filtered = assets.filter(a => {
    const matchesSearch = !filter || 
      a.symbol.toLowerCase().includes(filter.toLowerCase()) ||
      a.name.toLowerCase().includes(filter.toLowerCase())
    const matchesSector = !sectorFilter || a.sector === sectorFilter
    const matchesData = !showOnlyAvailable || a.has_data
    return matchesSearch && matchesSector && matchesData
  })

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-semibold text-slate-100">Markets</h1>
        <div className="text-slate-400 text-sm">
          {lakehouse ? `${lakehouse.total_files} / ${assets.length} assets populated` : 'Loading...'}
        </div>
      </div>

      {/* Filters */}
      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4 flex gap-4 items-center flex-wrap">
        <input
          type="text"
          placeholder="Search symbol or name..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="bg-slate-800 border border-slate-700 rounded px-3 py-2 text-slate-100 text-sm focus:outline-none focus:border-blue-500"
        />
        <select
          value={sectorFilter}
          onChange={(e) => setSectorFilter(e.target.value)}
          className="bg-slate-800 border border-slate-700 rounded px-3 py-2 text-slate-100 text-sm focus:outline-none focus:border-blue-500"
        >
          <option value="">All Sectors</option>
          {sectors.map(s => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <label className="flex items-center gap-2 text-slate-300 text-sm">
          <input
            type="checkbox"
            checked={showOnlyAvailable}
            onChange={(e) => setShowOnlyAvailable(e.target.checked)}
            className="rounded border-slate-700 bg-slate-800"
          />
          Show only with data
        </label>
      </div>

      {/* Asset Table */}
      <div className="bg-slate-900/50 border border-slate-800 rounded-lg overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-slate-400">Loading assets...</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-slate-400 border-b border-slate-800 bg-slate-900/80">
                  <th className="text-left px-4 py-3">Symbol</th>
                  <th className="text-left px-4 py-3">Name</th>
                  <th className="text-left px-4 py-3">Sector</th>
                  <th className="text-left px-4 py-3">Industry</th>
                  <th className="text-center px-4 py-3">Data</th>
                  <th className="text-right px-4 py-3">Latest</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((asset) => (
                  <tr key={asset.symbol} className="border-b border-slate-800/50 hover:bg-slate-800/30">
                    <td className="px-4 py-3 font-mono text-slate-200">{asset.symbol}</td>
                    <td className="px-4 py-3 text-slate-300">{asset.name}</td>
                    <td className="px-4 py-3 text-slate-400">{asset.sector || '-'}</td>
                    <td className="px-4 py-3 text-slate-500">{asset.industry || '-'}</td>
                    <td className="px-4 py-3 text-center">
                      {asset.has_data ? (
                        <span className="text-emerald-400">✓</span>
                      ) : (
                        <span className="text-rose-400">○</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right text-slate-500 text-xs">
                      {asset.latest_date || '-'}
                    </td>
                  </tr>
                ))}
                {filtered.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                      No assets match your filters
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
        {!loading && (
          <div className="px-4 py-3 text-slate-500 text-xs border-t border-slate-800">
            Showing {filtered.length} of {assets.length} assets
            {lakehouse && ` • ${lakehouse.total_bars_ingested.toLocaleString()} total bars`}
          </div>
        )}
      </div>
    </div>
  )
}
