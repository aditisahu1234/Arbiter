import { LakehouseStatus } from '../types'
import { Database, HardDrive, RefreshCw } from 'lucide-react'

interface HeaderProps {
  status: LakehouseStatus | null
  onRefresh: () => void
  isRefreshing: boolean
}

export function Header({ status, onRefresh, isRefreshing }: HeaderProps) {
  return (
    <header className="border-b border-[#1e2638] bg-[#0d111a] px-6 py-4">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-3">
            <span className="text-xl font-bold font-mono tracking-wider text-blue-500">ARBITER</span>
            <span className="text-xs px-2 py-0.5 rounded bg-blue-950 text-blue-300 border border-blue-800 font-mono">
              QUANT TERMINAL v0.1
            </span>
            <span className="flex items-center space-x-1 text-xs text-emerald-400">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
              <span>LIVE</span>
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Startup-Grade Quantitative Market Analysis & Strategy Research Platform
          </p>
        </div>

        {/* Telemetry Cards */}
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2 bg-[#111622] border border-[#1e2638] px-3 py-1.5 rounded-lg text-xs font-mono">
            <Database className="w-3.5 h-3.5 text-blue-400" />
            <span className="text-slate-400">Lakehouse Parquet:</span>
            <span className="text-slate-100 font-bold">{status?.total_files ?? 0} Assets</span>
          </div>

          <div className="flex items-center space-x-2 bg-[#111622] border border-[#1e2638] px-3 py-1.5 rounded-lg text-xs font-mono">
            <HardDrive className="w-3.5 h-3.5 text-emerald-400" />
            <span className="text-slate-400">Bars Ingested:</span>
            <span className="text-slate-100 font-bold">{status?.total_bars_ingested?.toLocaleString() ?? 0}</span>
          </div>

          <button
            onClick={onRefresh}
            disabled={isRefreshing}
            className="flex items-center space-x-1.5 bg-[#1e2638] hover:bg-[#2a364f] text-slate-200 px-3 py-1.5 rounded-lg text-xs font-mono transition-colors disabled:opacity-50"
            title="Refresh Lakehouse Status"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
            <span>Sync</span>
          </button>
        </div>
      </div>
    </header>
  )
}
