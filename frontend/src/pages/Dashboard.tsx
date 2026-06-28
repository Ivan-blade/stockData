import { useEffect, useState } from 'react'
import { useThemeStore } from '../stores/themeStore'
import { useCompanyStore } from '../stores/companyStore'

export default function Dashboard() {
  const { theme } = useThemeStore()
  const { cache, loadCache } = useCompanyStore()
  const [stats, setStats] = useState({ total: 0, a: 0, hk: 0 })
  const [searchInput, setSearchInput] = useState('')
  const isDark = theme === 'dark'
  const t = (d:string) => isDark ? d : d.replace('bg-[#0f1117]','bg-white').replace('border-[#1e2235]','border-gray-200').replace('bg-[#1a1d28]','bg-gray-100').replace('text-[#5a6275]','text-gray-400').replace('text-[#8892a4]','text-gray-500').replace('hover:bg-purple-500/5','hover:bg-purple-50/50').replace('text-[#e8eaed]','text-[#1a1d2e]')

  useEffect(() => {
    useCompanyStore.getState().loadCache().then(all => {
      setStats({ total: all.length, a: all.filter(c=>c.exchange!=='HK').length, hk: all.filter(c=>c.exchange==='HK').length })
    })
    fetchLatestSnapshot()
  }, [])

  const [snap, setSnap] = useState<{date:string; total:number; has_pe:number; items:any[]} | null>(null)
  const fetchLatestSnapshot = async () => {
    try {
      const res = await fetch('/api/snapshots/latest')
      const d = await res.json()
      setSnap(d)
    } catch {}
  }

  // 合并快照数据 + 公司名称
  const rawRows = (snap?.items || []).map(item => {
    const company = cache.find(c => c.code === item.code)
    return { ...item, name: company?.name || '-' }
  }).filter(r => {
    if (!searchInput) return true
    return r.name.includes(searchInput) || r.code.includes(searchInput)
  })

  // 排序
  const [sortKey, setSortKey] = useState<string>('')
  const [sortAsc, setSortAsc] = useState(true)
  let snapshotRows = [...rawRows]
  if (sortKey) {
    snapshotRows.sort((a, b) => {
      const av = a[sortKey] ?? 0
      const bv = b[sortKey] ?? 0
      if (typeof av === 'string') return sortAsc ? av.localeCompare(bv) : bv.localeCompare(av)
      return sortAsc ? (av as number) - (bv as number) : (bv as number) - (av as number)
    })
  }

  const toggleSort = (key: string) => {
    if (sortKey === key) {
      if (sortAsc) setSortAsc(false)
      else setSortKey('')  // 第三次点击取消排序
    } else { setSortKey(key); setSortAsc(true) }
  }
  const sortIcon = (key: string) => {
    if (sortKey !== key) return ''
    return sortAsc ? ' ▲' : ' ▼'
  }

  // 分页
  const pageSize = 10
  const [page, setPage] = useState(1)
  const totalPages = Math.ceil(snapshotRows.length / pageSize) || 1
  const pagedRows = snapshotRows.slice((page - 1) * pageSize, page * pageSize)

  useEffect(() => { setPage(1) }, [searchInput])

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-base font-semibold">数据概览</h2>
        <span className={`text-xs px-2 py-0.5 rounded ${isDark ? 'bg-[#1a1d28] text-[#5a6275]' : 'bg-gray-100 text-gray-400'}`}>
          ✅ API
        </span>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-3 mb-6">
        {[
          { label: '公司总数', value: stats.total, cls: 'text-[#f5c842]' },
          { label: 'A 股', value: stats.a, cls: 'text-green-500' },
          { label: '港 股', value: stats.hk, cls: 'text-blue-500' },
          { label: snap ? `估值快照 ${snap.date?.slice(5)}` : '估值快照', value: snap ? `${snap.has_pe}/${snap.total}` : '--', cls: '' },
        ].map(s => (
          <div key={s.label} className={`rounded-xl p-5 border ${isDark ? 'bg-[#0f1117] border-[#1e2235]' : 'bg-white border-gray-200'}`}>
            <div className={`text-xs tracking-wider mb-1.5 ${t('text-[#8892a4]')}`}>{s.label}</div>
            <div className={`text-[28px] font-bold font-mono ${s.cls} ${!s.cls && (isDark ? 'text-white' : 'text-gray-900')}`}>{s.value}</div>
          </div>
        ))}
      </div>

      {/* Search bar */}
      <div className="flex items-center gap-3 mb-4">
        <h2 className="text-base font-semibold">行情快照</h2>
        <span className={`text-xs ${t('text-[#5a6275]')}`}>{snap?.date ? `更新于 ${snap.date}` : ''}</span>
        <input
          value={searchInput}
          onChange={e => setSearchInput(e.target.value)}
          placeholder="搜索公司名称..."
          className={`flex-1 max-w-xs px-3 py-1.5 text-sm rounded-md border outline-none ${isDark ? 'bg-[#1a1d28] border-[#1e2235] text-white placeholder-[#5a6275]' : 'bg-white border-gray-200 text-gray-800 placeholder-gray-400'}`}
        />
      </div>

      <div className={`rounded-xl overflow-hidden border ${t('bg-[#0f1117] border-[#1e2235]')}`}>
        <table className="w-full">
          <thead>
            <tr className={`text-left text-[11px] font-semibold uppercase tracking-wider ${t('bg-[#1a1d28] text-[#5a6275]')}`}>
              {['代码','名称','收盘价','涨跌幅','换手率','PE','PB','市值'].map((h, i) => {
                const keys = ['code','name','close','change_pct','turnover','pe_ttm','pb','market_cap']
                const k = keys[i]
                return <th key={h} onClick={() => toggleSort(k)} className={`px-3.5 py-2.5 ${i < 2 ? 'text-left' : 'text-right'} cursor-pointer transition-colors select-none ${isDark ? 'hover:text-white' : 'hover:text-gray-800'}`}>{h}{sortIcon(k)}</th>
              })}
            </tr>
          </thead>
          <tbody>
            {pagedRows.map(r => (
              <tr key={r.code} className={`border-b ${t('border-[#1e2235]/50 hover:bg-purple-500/5')}`}>
                <td className={`px-3.5 py-2 text-xs font-mono ${t('text-[#5a6275]')}`}>{r.code}</td>
                <td className="px-3.5 py-2 text-sm font-medium">{r.name}</td>
                <td className={`px-3.5 py-2 text-sm font-mono text-right`}>{r.close?.toFixed(2)}</td>
                <td className={`px-3.5 py-2 text-sm font-mono text-right ${(r.change_pct||0) > 0 ? 'text-green-500' : (r.change_pct||0) < 0 ? 'text-red-500' : ''}`}>
                  {(r.change_pct||0) > 0 ? '+' : ''}{r.change_pct?.toFixed(2)}%
                </td>
                <td className={`px-3.5 py-2 text-xs font-mono text-right ${t('text-[#8892a4]')}`}>{r.turnover?.toFixed(2)}%</td>
                <td className={`px-3.5 py-2 text-xs font-mono text-right ${(r.pe_ttm||0) > 0 ? '' : t('text-[#5a6275]')}`}>
                  {(r.pe_ttm||0) > 0 ? r.pe_ttm?.toFixed(2) : '-'}
                </td>
                <td className={`px-3.5 py-2 text-xs font-mono text-right ${t('text-[#8892a4]')}`}>{r.pb?.toFixed(2)}</td>
                <td className={`px-3.5 py-2 text-xs font-mono text-right ${t('text-[#5a6275]')}`}>
                  {r.market_cap ? (r.market_cap / 1e8).toFixed(0) + '亿' : '-'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between mt-3">
        <span className={`text-xs ${t('text-[#5a6275]')}`}>共 {snapshotRows.length} 条，{(page-1)*pageSize+1}-{Math.min(page*pageSize, snapshotRows.length)}</span>
        <div className="flex items-center gap-2">
          <button disabled={page<=1} onClick={()=>setPage(page-1)} className={`px-3 py-1 text-xs rounded-md border cursor-pointer disabled:opacity-30 ${t('bg-[#1a1d28] border-[#1e2235] text-[#8892a4]')}`}>上一页</button>
          {Array.from({length: Math.min(totalPages, 5)}, (_,i)=>{
            const pg = Math.max(1, Math.min(page-2, totalPages-4)) + i
            if (pg > totalPages) return null
            return <button key={pg} onClick={()=>setPage(pg)} className={`px-2.5 py-1 text-xs rounded-md border cursor-pointer ${pg===page ? 'bg-amber-500/20 border-amber-500/50 text-amber-500' : t('bg-[#1a1d28] border-[#1e2235] text-[#8892a4]')}`}>{pg}</button>
          })}
          <button disabled={page>=totalPages} onClick={()=>setPage(page+1)} className={`px-3 py-1 text-xs rounded-md border cursor-pointer disabled:opacity-30 ${t('bg-[#1a1d28] border-[#1e2235] text-[#8892a4]')}`}>下一页</button>
        </div>
      </div>
    </div>
  )
}
