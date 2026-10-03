import { useEffect, useState, useCallback } from 'react'
import { Header } from './components/Header'
import { UniverseBar } from './components/UniverseBar'
import { AssetTable } from './components/AssetTable'
import { CandlestickChart } from './components/CandlestickChart'
import { OhlcvTable } from './components/OhlcvTable'
import {
  fetchAssets,
  fetchAssetOhlcv,
  fetchLakehouseStatus,
  fetchUniverses,
  triggerIngestion,
} from './services/api'
import { Asset, LakehouseStatus, OhlcBar, Universe } from './types'

export default function App() {
  const [universes, setUniverses] = useState<Universe[]>([])
  const [selectedUniverse, setSelectedUniverse] = useState<string>('')
  const [assets, setAssets] = useState<Asset[]>([])
  const [totalAssets, setTotalAssets] = useState<number>(0)
  const [searchTerm, setSearchTerm] = useState<string>('')
  const [selectedSymbol, setSelectedSymbol] = useState<string>('RELIANCE')
  const [ohlcvData, setOhlcvData] = useState<OhlcBar[]>([])
  const [lakehouseStatus, setLakehouseStatus] = useState<LakehouseStatus | null>(null)
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false)
  const [ingestingSymbol, setIngestingSymbol] = useState<string | null>(null)
  const [notification, setNotification] = useState<string | null>(null)

  // Load Universes & Lakehouse telemetry
  const loadInitialData = useCallback(async () => {
    setIsRefreshing(true)
    try {
      const [uData, lData] = await Promise.all([
        fetchUniverses(),
        fetchLakehouseStatus(),
      ])
      setUniverses(uData)
      setLakehouseStatus(lData)
    } catch (err) {
      console.error('Error fetching initial platform data:', err)
    } finally {
      setIsRefreshing(false)
    }
  }, [])

  useEffect(() => {
    loadInitialData()
  }, [loadInitialData])

  // Load Assets when universe or search changes
  useEffect(() => {
    const handler = setTimeout(async () => {
      try {
        const res = await fetchAssets({
          universe: selectedUniverse || undefined,
          search: searchTerm || undefined,
          limit: 100,
        })
        setAssets(res.items)
        setTotalAssets(res.total)
      } catch (err) {
        console.error('Error loading assets:', err)
      }
    }, 200)

    return () => clearTimeout(handler)
  }, [selectedUniverse, searchTerm])

  // Load OHLCV when selected asset changes
  const loadOhlcv = useCallback(async (symbol: string) => {
    try {
      const res = await fetchAssetOhlcv(symbol)
      setOhlcvData(res.data)
    } catch (err) {
      console.error(`Error loading OHLCV for ${symbol}:`, err)
      setOhlcvData([])
    }
  }, [])

  useEffect(() => {
    if (selectedSymbol) {
      loadOhlcv(selectedSymbol)
    }
  }, [selectedSymbol, loadOhlcv])

  // Trigger dynamic ingestion
  const handleIngest = async (symbol: string) => {
    setIngestingSymbol(symbol)
    setNotification(`Fetching 5-year historical market data for ${symbol} from Yahoo Finance...`)
    try {
      const res = await triggerIngestion(symbol)
      if (res.status === 'success') {
        setNotification(
          `Successfully ingested ${res.rows_ingested} daily bars for ${symbol} into Parquet Lakehouse!`
        )
        // Refresh telemetry and reload asset OHLCV
        const lData = await fetchLakehouseStatus()
        setLakehouseStatus(lData)
        setSelectedSymbol(symbol)
        await loadOhlcv(symbol)

        // Refresh asset table
        const aRes = await fetchAssets({
          universe: selectedUniverse || undefined,
          search: searchTerm || undefined,
          limit: 100,
        })
        setAssets(aRes.items)
      } else {
        setNotification(`Ingestion response: ${res.status}. Check backend logs.`)
      }
    } catch (err: any) {
      setNotification(`Failed to ingest ${symbol}: ${err.message}`)
    } finally {
      setIngestingSymbol(null)
      setTimeout(() => setNotification(null), 5000)
    }
  }

  return (
    <div className="min-h-screen bg-[#0a0d14] text-slate-100 flex flex-col font-sans selection:bg-blue-600 selection:text-white">
      {/* Top Telemetry Header */}
      <Header
        status={lakehouseStatus}
        onRefresh={loadInitialData}
        isRefreshing={isRefreshing}
      />

      {/* Universe Filter Bar */}
      <UniverseBar
        universes={universes}
        selectedUniverse={selectedUniverse}
        onSelectUniverse={setSelectedUniverse}
        totalCatalogAssets={512}
      />

      {/* Dynamic Toast / Status Banner */}
      {notification && (
        <div className="bg-blue-950/80 border-b border-blue-800 text-blue-200 px-6 py-2 text-xs font-mono flex items-center justify-between transition-all">
          <span>{notification}</span>
          <button
            onClick={() => setNotification(null)}
            className="text-slate-400 hover:text-white ml-4"
          >
            ✕
          </button>
        </div>
      )}

      {/* Main Terminal Workspace */}
      <main className="flex-1 p-6 grid grid-cols-1 lg:grid-cols-12 gap-6 overflow-hidden">
        {/* Left Column: Asset Selection Table */}
        <section className="lg:col-span-5 flex flex-col h-full">
          <AssetTable
            assets={assets}
            total={totalAssets}
            selectedSymbol={selectedSymbol}
            onSelectSymbol={setSelectedSymbol}
            onIngest={handleIngest}
            ingestingSymbol={ingestingSymbol}
            searchTerm={searchTerm}
            onSearchChange={setSearchTerm}
          />
        </section>

        {/* Right Column: Chart & OHLCV Lakehouse Inspector */}
        <section className="lg:col-span-7 flex flex-col space-y-6">
          <CandlestickChart data={ohlcvData} symbol={selectedSymbol} />
          <OhlcvTable data={ohlcvData} />
        </section>
      </main>
    </div>
  )
}
