import { Asset, LakehouseStatus, OhlcResponse, Universe } from '../types'

const API_BASE = '/api/v1'

export async function fetchUniverses(): Promise<Universe[]> {
  const res = await fetch(`${API_BASE}/universes`)
  if (!res.ok) throw new Error('Failed to fetch universes')
  return res.json()
}

export async function fetchAssets(params: {
  universe?: string
  search?: string
  sector?: string
  skip?: number
  limit?: number
}): Promise<{ total: number; items: Asset[] }> {
  const query = new URLSearchParams()
  if (params.universe) query.set('universe', params.universe)
  if (params.search) query.set('search', params.search)
  if (params.sector) query.set('sector', params.sector)
  if (params.skip !== undefined) query.set('skip', params.skip.toString())
  if (params.limit !== undefined) query.set('limit', params.limit.toString())

  const res = await fetch(`${API_BASE}/assets?${query.toString()}`)
  if (!res.ok) throw new Error('Failed to fetch assets')
  return res.json()
}

export async function fetchLakehouseStatus(): Promise<LakehouseStatus> {
  const res = await fetch(`${API_BASE}/market-data/lakehouse`)
  if (!res.ok) throw new Error('Failed to fetch lakehouse status')
  return res.json()
}

export async function fetchAssetOhlcv(symbol: string, limit = 1250): Promise<OhlcResponse> {
  const res = await fetch(`${API_BASE}/assets/${symbol}/ohlcv?limit=${limit}`)
  if (!res.ok) throw new Error(`Failed to fetch OHLCV for ${symbol}`)
  return res.json()
}

export async function triggerIngestion(symbol: string, years = 5): Promise<any> {
  const res = await fetch(`${API_BASE}/market-data/ingest/${symbol}?years=${years}`, {
    method: 'POST',
  })
  if (!res.ok) throw new Error(`Failed to ingest ${symbol}`)
  return res.json()
}

export async function fetchHealth(): Promise<any> {
  const res = await fetch('/health')
  if (!res.ok) throw new Error('Health check failed')
  return res.json()
}

export async function fetchSMA(symbol: string, window = 20): Promise<any> {
  const res = await fetch(`${API_BASE}/indicators/sma?symbol=${symbol}&window=${window}`)
  if (!res.ok) throw new Error(`Failed to fetch SMA for ${symbol}`)
  return res.json()
}

export async function fetchATR(symbol: string, w = 14): Promise<any> {
  const res = await fetch(`${API_BASE}/indicators/atr?symbol=${symbol}&window=${w}`)
  if (!res.ok) throw new Error(`Failed to fetch ATR for ${symbol}`)
  return res.json()
}

export async function runBacktest(params: {
  symbol: string
  fast_sma?: number
  slow_sma?: number
  atr_window?: number
  atr_mult?: number
  cost_bps?: number
}): Promise<any> {
  const query = new URLSearchParams({ symbol: params.symbol })
  if (params.fast_sma) query.set('fast_sma', params.fast_sma.toString())
  if (params.slow_sma) query.set('slow_sma', params.slow_sma.toString())
  if (params.atr_window) query.set('atr_window', params.atr_window.toString())
  if (params.atr_mult) query.set('atr_mult', params.atr_mult.toString())
  if (params.cost_bps) query.set('cost_bps', params.cost_bps.toString())

  const res = await fetch(`${API_BASE}/strategies/backtest?${query.toString()}`, {
    method: 'POST',
  })
  if (!res.ok) throw new Error('Backtest failed')
  return res.json()
}

export async function runCAPM(params: {
  symbol: string
  risk_free_annual?: number
}): Promise<any> {
  const query = new URLSearchParams({ symbol: params.symbol })
  if (params.risk_free_annual) query.set('risk_free_annual', params.risk_free_annual.toString())
  const res = await fetch(`${API_BASE}/risk/capm?${query.toString()}`)
  if (!res.ok) throw new Error('CAPM failed')
  return res.json()
}

export async function runFF3(params: {
  symbol: string
  factor_source?: string
}): Promise<any> {
  const query = new URLSearchParams({ symbol: params.symbol })
  if (params.factor_source) query.set('factor_source', params.factor_source)
  const res = await fetch(`${API_BASE}/risk/fama-french?${query.toString()}`)
  if (!res.ok) throw new Error('FF3 failed')
  return res.json()
}

export async function fetchDataStatus(symbol: string): Promise<any> {
  const res = await fetch(`${API_BASE}/positions/${symbol}/data-status`)
  if (!res.ok) throw new Error(`Failed to fetch data status for ${symbol}`)
  return res.json()
}

export async function refreshAssetData(symbol: string): Promise<any> {
  const res = await fetch(`${API_BASE}/positions/${symbol}/refresh-data`, {
    method: 'POST',
  })
  if (!res.ok) throw new Error(`Failed to refresh data for ${symbol}`)
  return res.json()
}

export async function fetchLiveQuote(symbol: string): Promise<any> {
  const res = await fetch(`${API_BASE}/positions/${symbol}/live-quote`)
  if (!res.ok) return { data_state: 'unavailable', price: null, note: 'Live quote unavailable' }
  return res.json()
}
