import { OhlcBar } from '../types'

interface OhlcvTableProps {
  data: OhlcBar[]
}

export function OhlcvTable({ data }: OhlcvTableProps) {
  // Show most recent 15 bars
  const recentData = [...data].reverse().slice(0, 15)

  if (recentData.length === 0) {
    return (
      <div className="p-8 text-center text-sm text-slate-500 bg-[#0d111a] border border-[#1e2638] rounded-lg">
        No OHLCV bars ingested yet. Click &quot;Ingest from Yahoo&quot; to fetch live 5-year data.
      </div>
    )
  }

  return (
    <div className="border border-[#1e2638] rounded-lg bg-[#0d111a] overflow-hidden">
      <div className="px-4 py-2.5 bg-[#111622] border-b border-[#1e2638] flex justify-between items-center">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
          Normalized OHLCV Data Inspector (Recent Bars)
        </h3>
        <span className="text-xs font-mono text-slate-500">Parquet / DuckDB Verified</span>
      </div>
      <div className="overflow-x-auto max-h-64">
        <table className="w-full text-left font-mono text-xs">
          <thead className="bg-[#0a0d14] text-slate-400 border-b border-[#1e2638] sticky top-0">
            <tr>
              <th className="py-2 px-3">Date</th>
              <th className="py-2 px-3 text-right">Open</th>
              <th className="py-2 px-3 text-right">High</th>
              <th className="py-2 px-3 text-right">Low</th>
              <th className="py-2 px-3 text-right">Close</th>
              <th className="py-2 px-3 text-right">Adj Close</th>
              <th className="py-2 px-3 text-right">Volume</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#182030] text-slate-200">
            {recentData.map((bar, idx) => {
              const isGreen = bar.close >= bar.open
              return (
                <tr key={idx} className="hover:bg-[#111622] transition-colors">
                  <td className="py-1.5 px-3 text-slate-400">{bar.time}</td>
                  <td className="py-1.5 px-3 text-right">₹{bar.open.toFixed(2)}</td>
                  <td className="py-1.5 px-3 text-right text-emerald-400">₹{bar.high.toFixed(2)}</td>
                  <td className="py-1.5 px-3 text-right text-rose-400">₹{bar.low.toFixed(2)}</td>
                  <td className={`py-1.5 px-3 text-right font-medium ${isGreen ? 'text-emerald-400' : 'text-rose-400'}`}>
                    ₹{bar.close.toFixed(2)}
                  </td>
                  <td className="py-1.5 px-3 text-right text-slate-300">₹{bar.adjusted_close.toFixed(2)}</td>
                  <td className="py-1.5 px-3 text-right text-slate-400">{bar.volume.toLocaleString()}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
