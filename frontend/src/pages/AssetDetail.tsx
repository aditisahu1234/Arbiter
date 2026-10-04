import { useEffect, useState } from 'react'
import { fetchAssetOhlcv, fetchSMA, fetchATR } from '../services/api'
import { OhlcBar } from '../types'

export default function AssetDetail({ symbol }: { symbol: string }) {
  const [ohlcv, setOhlcv] = useState<OhlcBar[]>([])
  const [sma, setSma] = useState<any>(null)
  const [atr, setAtr] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const loadData = async () => {
      if (!symbol) return
      setLoading(true)
      try {
        const [ohlc, smaData, atrData] = await Promise.all([
          fetchAssetOhlcv(symbol),
          fetchSMA(symbol, 20),
          fetchATR(symbol, 14),
        ])
        setOhlcv(ohlc.data)
        setSma(smaData)
        setAtr(atrData)
      } catch (err) {
        console.error('Asset detail load failed:', err)
      } finally {
        setLoading(false)
      }
    }
    loadData()
  }, [symbol])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-slate-400">Loading {symbol}...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-slate-100">{symbol} - Asset Detail</h1>
      
      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
        <h2 className="text-lg font-semibold text-slate-100 mb-4">OHLCV Data</h2>
        <div className="text-slate-400 text-sm">
          <p>Bars: {ohlcv.length}</p>
          {ohlcv.length > 0 && (
            <p className="text-slate-500">
              Range: {ohlcv[0].time} to {ohlcv[ohlcv.length - 1].time}
            </p>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
          <h3 className="text-slate-300 font-medium">SMA(20)</h3>
          <p className="text-slate-500 text-sm">
            {sma?.data?.length || 0} bars
          </p>
        </div>
        <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
          <h3 className="text-slate-300 font-medium">ATR(14)</h3>
          <p className="text-slate-500 text-sm">
            {atr?.data?.length || 0} bars
          </p>
        </div>
      </div>
    </div>
  )
}
