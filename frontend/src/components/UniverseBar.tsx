import { Universe } from '../types'

interface UniverseBarProps {
  universes: Universe[]
  selectedUniverse: string
  onSelectUniverse: (universeName: string) => void
  totalCatalogAssets: number
}

export function UniverseBar({
  universes,
  selectedUniverse,
  onSelectUniverse,
  totalCatalogAssets,
}: UniverseBarProps) {
  return (
    <div className="flex items-center space-x-2 overflow-x-auto py-2 px-6 bg-[#0a0d14] border-b border-[#1e2638] text-xs font-mono">
      <span className="text-slate-500 uppercase tracking-wider text-[10px] font-semibold mr-2">
        Universe:
      </span>
      <button
        onClick={() => onSelectUniverse('')}
        className={`px-3 py-1 rounded-md transition-colors whitespace-nowrap ${
          selectedUniverse === ''
            ? 'bg-blue-600 text-white font-medium shadow-sm'
            : 'bg-[#111622] text-slate-400 hover:bg-[#1e2638] hover:text-slate-200 border border-[#1e2638]'
        }`}
      >
        All Equities ({totalCatalogAssets})
      </button>

      {universes.map((u) => {
        const isSelected = selectedUniverse === u.name
        return (
          <button
            key={u.id}
            onClick={() => onSelectUniverse(u.name)}
            className={`px-3 py-1 rounded-md transition-colors whitespace-nowrap ${
              isSelected
                ? 'bg-blue-600 text-white font-medium shadow-sm'
                : 'bg-[#111622] text-slate-400 hover:bg-[#1e2638] hover:text-slate-200 border border-[#1e2638]'
            }`}
          >
            {u.name} ({u.member_count})
          </button>
        )
      })}
    </div>
  )
}
