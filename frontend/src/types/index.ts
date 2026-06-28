export interface Company {
  code: string
  name: string
  exchange: string
  industry: string | null
  business_scope: string | null
  listing_date: string | null
  total_shares: number | null
  employees: number | null
  website: string | null
}

export interface FinancialResponse {
  summary: Record<string, Record<string, number>>
  indicators: Record<string, Record<string, number>>
}

export interface Stats {
  total: number
  aShares: number
  hkShares: number
  financialRecords: number
}
