export interface Asset {
  id: number
  symbol: string
  name: string
  exchange: string
  sector: string | null
  industry: string | null
  provider_symbol: string
  has_data: boolean
  latest_date: string | null
}

export interface Universe {
  id: number
  name: string
  display_name: string
  description: string | null
  is_active: boolean
  member_count: number
}

export interface LakehouseFileStat {
  symbol: string
  filename: string
  size_kb: number
  rows: number
  latest_date: string | null
}

export interface LakehouseStatus {
  lakehouse_dir: string
  total_files: number
  total_bars_ingested: number
  total_size_mb: number
  latest_date?: string | null
  assets: LakehouseFileStat[]
}

export interface OhlcBar {
  time: string
  open: number
  high: number
  low: number
  close: number
  adjusted_close: number
  volume: number
}

export interface OhlcResponse {
  symbol: string
  count: number
  first_date: string | null
  last_date: string | null
  data: OhlcBar[]
  message?: string
}
