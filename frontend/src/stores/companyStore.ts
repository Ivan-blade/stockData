import { create } from 'zustand'
import { api, type CompanyListRes } from '../api/client'
import type { Company } from '../types'

interface CompanyStore {
  // 全量缓存（各个页面复用）
  cache: Company[]
  cacheLoaded: boolean
  loadCache: () => Promise<Company[]>

  // 分页列表
  page: number
  keyword: string
  total: number
  companies: Company[]
  loading: boolean
  setKeyword: (kw: string) => void
  setPage: (p: number) => void
  load: (kw?: string, pg?: number) => Promise<void>
}

export const useCompanyStore = create<CompanyStore>((set, get) => ({
  cache: [],
  cacheLoaded: false,
  companies: [],
  page: 1,
  keyword: '',
  total: 0,
  loading: false,

  loadCache: async () => {
    const s = get()
    if (s.cacheLoaded && s.cache.length > 0) return s.cache
    try {
      const res = await api.companies.list('', 1, 200)
      set({ cache: res.items, cacheLoaded: true })
      return res.items
    } catch { return [] }
  },

  setKeyword: (kw: string) => {
    set({ keyword: kw, page: 1 })
    get().load(kw, 1)
  },

  setPage: (p: number) => {
    set({ page: p })
    get().load(get().keyword, p)
  },

  load: async (kw?: string, pg?: number) => {
    set({ loading: true })
    try {
      const k = kw ?? get().keyword
      const p = pg ?? get().page
      const res = await api.companies.list(k, p, 20)
      set({ companies: res.items, total: res.total, page: res.page, loading: false })
    } catch { set({ loading: false }) }
  },
}))
