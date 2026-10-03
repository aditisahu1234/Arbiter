import { Asset } from '../types'
import { CheckCircle2, Download, Search } from 'lucide-react'

interface AssetTableProps {
  assets: Asset[]
  total: number
  selectedSymbol: string
  onSelectSymbol: (symbol: string) => void
  onIngest: (symbol: string) => void
  ingestingSymbol: string | null
  searchTerm: string
  onSearchChange: (value: string) => void
}

export function AssetTable({
  assets,
  total,
  selectedSymbol,
  onSelectSymbol,
  onIngest,
  ingestingSymbol,
  searchTerm,
  onSearchChange,
}: AssetTableProps) {
  return (
    <div className="flex flex-col h-full border border-[#1e2638] rounded-lg bg-[#0d111a] overflow-hidden">
      {/* Table Header & Search */}
      <div className="p-3 bg-[#111622] border-b border-[#1e2638] flex items-center justify-between gap-3">
        <div className="relative flex-1">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search symbol, company name (e.g. TCS, Reliance)..."
            value={searchTerm}
            onChange={(e) => onSearchChange(e.target.value)}
            className="w-full bg-[#0a0d14] border border-[#1e2638] rounded-md pl-9 pr-3 py-1.5 text-xs text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-blue-500 font-mono"
          />
        </div>
        <span className="text-xs font-mono text-slate-400 whitespace-nowrap">
          {total} Matching Assets
        </span>
      </div>

      {/* Asset List */}
      <div className="flex-1 overflow-y-auto max-h-[460px]">
        <table className="w-full text-left text-xs font-mono">
          <thead className="bg-[#0a0d14] text-slate-400 border-b border-[#1e2638] sticky top-0">
            <tr>
              <th className="py-2 px-3">Symbol</th>
              <th className="py-2 px-3">Company</th>
              <th className="py-2 px-3">Sector</th>
              <th className="py-2 px-3">Lakehouse Status</th>
              <th className="py-2 px-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#182030]">
            {assets.map((asset) => {
              const isSelected = asset.symbol === selectedSymbol
              const isIngesting = ingestingSymbol === asset.symbol

              return (
                <tr
                  key={asset.id}
                  onClick={() => onSelectSymbol(asset.symbol)}
                  className={`cursor-pointer transition-colors ${
                    isSelected
                      ? 'bg-blue-950/40 border-l-2 border-blue-500'
                      : 'hover:bg-[#111622]'
                  }`}
                >
                  <td className="py-2 px-3 font-bold text-slate-200">{asset.symbol}</td>
                  <td className="py-2 px-3 text-slate-300 max-w-[180px] truncate" title={asset.name}>
                    {asset.name}
                  </td>
                  <td className="py-2 px-3 text-slate-400">{asset.sector || 'N/A'}</td>
                  <td className="py-2 px-3">
                    {asset.has_data ? (
                      <span className="inline-flex items-center space-x-1 text-[11px] text-emerald-400 bg-emerald-950/40 px-2 py-0.5 rounded border border-emerald-800">
                        <CheckCircle2 className="w-3 h-3" />
                        <span>Ingested</span>
                      </span>
                    ) : (
                      <span className="inline-flex items-center text-[11px] text-slate-500 bg-slate-900 px-2 py-0.5 rounded border border-slate-800">
                        Not Ingested
                      </span>
                    )}
                  </td>
                  <td className="py-2 px-3 text-right">
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        onIngest(asset.symbol)
                      }}
                      disabled={isIngesting}
                      className="inline-flex items-center space-x-1 px-2 py-1 rounded bg-[#1e2638] hover:bg-blue-600 hover:text-white text-slate-300 text-[11px] transition-colors disabled:opacity-50"
                      title="Fetch live 5-year OHLCV from Yahoo Finance"
                    >
                      <Download className={`w-3 h-3 ${isIngesting ? 'animate-bounce' : ''}`} />
                      <span>{isIngesting ? 'Fetching...' : 'Ingest Yahoo'}</span>
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
