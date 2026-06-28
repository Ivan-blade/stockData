import type { Company } from '../types'

const BASE = ''

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`)
  return res.json()
}

export interface CompanyListRes {
  total: number
  page: number
  page_size: number
  items: Company[]
}

export const api = {
  companies: {
    list: (keyword = '', page = 1, pageSize = 20) =>
      get<CompanyListRes>(`/api/companies?keyword=${encodeURIComponent(keyword)}&page=${page}&page_size=${pageSize}`),
    full: () => get<{total: number; page: number; page_size: number; items: Company[]}>(`/api/companies?page=1&page_size=200`),
    detail: (code: string) => get<Company>(`/api/companies/${code}`),
    financial: (code: string) => get<{summary: Record<string, Record<string, number>>}>(`/api/companies/${code}/financial`),
  },
  collect: {
    all: () => get<{ok: boolean; elapsed: string; stats: any}>('/api/collect'),
    one: (code: string) => get<{ok: boolean; elapsed: string; stats: any}>(`/api/collect/${code}`),
  },
}
