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
