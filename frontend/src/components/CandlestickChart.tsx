import { useEffect, useRef } from 'react'
import { createChart, IChartApi, ISeriesApi, ColorType } from 'lightweight-charts'
import { OhlcBar } from '../types'

interface CandlestickChartProps {
  data: OhlcBar[]
  symbol: string
}

export function CandlestickChart({ data, symbol }: CandlestickChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null)
  const smaFastRef = useRef<ISeriesApi<'Line'> | null>(null)
  const smaSlowRef = useRef<ISeriesApi<'Line'> | null>(null)
  const markersRef = useRef<any[]>([])

  useEffect(() => {
    if (!chartContainerRef.current) return

    const container = chartContainerRef.current
    const chart = createChart(container, {
      layout: {
        background: { type: ColorType.Solid, color: '#0d111a' },
        textColor: '#94a3b8',
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 12,
      },
      grid: {
        vertLines: { color: '#182030' },
        horzLines: { color: '#182030' },
      },
      crosshair: {
        mode: 0,
        vertLine: { color: '#3b82f6', width: 1, style: 3 },
        horzLine: { color: '#3b82f6', width: 1, style: 3 },
      },
      rightPriceScale: {
        borderColor: '#1e2638',
      },
      timeScale: {
        borderColor: '#1e2638',
        timeVisible: true,
      },
      width: container.clientWidth,
      height: 420,
    })

    const candleSeries = chart.addCandlestickSeries({
      upColor: '#10b981',
      downColor: '#ef4444',
      borderVisible: false,
      wickUpColor: '#10b981',
      wickDownColor: '#ef4444',
    })

    const volumeSeries = chart.addHistogramSeries({
      color: '#2563eb',
      priceFormat: {
        type: 'volume',
      },
      priceScaleId: '',
    })

    // Add SMA lines
    const smaFast = chart.addLineSeries({
      color: '#f59e0b',
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
    })
    smaFastRef.current = smaFast

    const smaSlow = chart.addLineSeries({
      color: '#8b5cf6',
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
    })
    smaSlowRef.current = smaSlow

    chart.priceScale('').applyOptions({
      scaleMargins: {
        top: 0.8,
        bottom: 0,
      },
    })

    chartRef.current = chart
    candleSeriesRef.current = candleSeries
    volumeSeriesRef.current = volumeSeries

    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
        })
      }
    }

    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      chart.remove()
    }
  }, [])

  useEffect(() => {
    if (!candleSeriesRef.current || !volumeSeriesRef.current || data.length === 0) return

    const candleData = data.map((d) => ({
      time: d.time,
      open: d.open,
      high: d.high,
      low: d.low,
      close: d.close,
    }))

    const volumeData = data.map((d) => ({
      time: d.time,
      value: d.volume,
      color: d.close >= d.open ? 'rgba(16, 185, 129, 0.4)' : 'rgba(239, 68, 68, 0.4)',
    }))

    candleSeriesRef.current.setData(candleData)
    volumeSeriesRef.current.setData(volumeData)

    if (chartRef.current) {
      chartRef.current.timeScale().fitContent()
    }
  }, [data])

  return (
    <div className="relative border border-[#1e2638] rounded-lg bg-[#0d111a] overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2.5 bg-[#111622] border-b border-[#1e2638]">
        <div className="flex items-center space-x-3">
          <span className="font-mono font-bold text-sm text-blue-400">{symbol}</span>
          <span className="text-xs text-slate-400">Daily OHLCV Candlestick Chart</span>
        </div>
        <div className="text-xs font-mono text-slate-400">
          {data.length > 0 ? (
            <span>
              {data.length} Bars | Range: <span className="text-slate-200">{data[0].time}</span> to{' '}
              <span className="text-slate-200">{data[data.length - 1].time}</span>
            </span>
          ) : (
            'No Data'
          )}
        </div>
      </div>
      <div ref={chartContainerRef} className="w-full" style={{ height: '420px' }} />
    </div>
  )
}
