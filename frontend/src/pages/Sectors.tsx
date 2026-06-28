import { useEffect, useState } from 'react'
import { useThemeStore } from '../stores/themeStore'

interface SectorItem {
  code: string
  name: string
  rank: number
  change_pct: number | null
  price: number | null
  turnover: number | null
  up_count: number | null
  down_count: number | null
  total_market_cap: number | null
  lead_stock: string
  lead_change: number | null
}

interface SectorRes {
  trade_date: string
  board_type: string
  total: number
  items: SectorItem[]
}

const API = ''

export default function Sectors() {
  const { theme } = useThemeStore()
  const isDark = theme === 'dark'
  const [tab, setTab] = useState<'industry' | 'concept'>('industry')
  const [sortBy, setSortBy] = useState('change_pct')
  const [data, setData] = useState<SectorRes | null>(null)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')

  const fetchSectors = async () => {
    setLoading(true)
    try {
      const r = await fetch(`${API}/api/sectors?board_type=${tab}&sort_by=${sortBy}&limit=200`)
      if (r.ok) setData(await r.json())
    } catch {}
    setLoading(false)
  }

  useEffect(() => { fetchSectors() }, [tab, sortBy])

  const sortOptions = [
    { key: 'change_pct', label: '涨跌幅' },
    { key: 'up_count', label: '上涨家数' },
    { key: 'turnover', label: '换手率' },
    { key: 'total_market_cap', label: '总市值' },
  ]

  const filtered = data?.items.filter(i =>
    !search || i.name.includes(search) || i.code.includes(search)
  ) ?? []

  const bg = (i: number) =>
    i % 2 === 0
      ? isDark ? 'bg-[#0f1117]/40' : 'bg-white'
      : isDark ? 'bg-[#0f1117]/60' : 'bg-gray-50/50'

  return (
    <div>
      {/* ── 头部 ── */}
      <div className="flex items-center gap-3 mb-3 flex-wrap">
        <h2 className="text-base font-semibold">板块排行</h2>
        <div className="flex rounded-md border overflow-hidden" style={{ borderColor: isDark ? '#1e2235' : '#d1d5db' }}>
          {(['industry', 'concept'] as const).map(t => (
            <button key={t}
              onClick={() => { setTab(t); setSearch('') }}
              className={`px-4 py-1 text-sm font-medium transition-colors ${
                tab === t
                  ? (isDark ? 'bg-amber-500/20 text-amber-400' : 'bg-amber-50 text-amber-600')
                  : (isDark ? 'text-[#8892a4] hover:text-white' : 'text-gray-500 hover:text-gray-900')
              }`}>
              {t === 'industry' ? '行业板块' : '概念板块'}
            </button>
          ))}
        </div>
        {data && (
          <span className={`text-xs ${isDark ? 'text-[#5a6275]' : 'text-gray-400'}`}>
            {data.trade_date} · {data.total} 个
          </span>
        )}
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="搜索板块..."
          className={`ml-auto w-44 px-3 py-1 text-xs rounded-md border outline-none ${
            isDark ? 'bg-[#1a1d28] border-[#1e2235] text-white placeholder-[#5a6275]' : 'bg-white border-gray-200 placeholder-gray-400'
          }`}
        />
      </div>

      {/* ── 排序按钮 ── */}
      <div className="flex gap-1.5 mb-3">
        {sortOptions.map(s => (
          <button key={s.key}
            onClick={() => setSortBy(s.key)}
            className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
              sortBy === s.key
                ? (isDark ? 'bg-amber-500/15 border-amber-500/30 text-amber-400' : 'bg-amber-50 border-amber-200 text-amber-600')
                : (isDark ? 'border-[#1e2235] text-[#5a6275] hover:text-white' : 'border-gray-200 text-gray-400 hover:text-gray-700')
            }`}>
            {s.label} ▾
          </button>
        ))}
      </div>

      {/* ── 表格 ── */}
      {loading ? (
        <div className="text-center py-16">
          <div className="w-8 h-8 border-3 border-t-amber-400 rounded-full animate-spin mx-auto"
            style={{ borderColor: isDark ? '#1e2235' : '#d1d5db', borderTopColor: '#f5c842' }}
          />
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border" style={{ borderColor: isDark ? '#1e2235' : '#e5e7eb' }}>
          <table className="w-full text-xs whitespace-nowrap">
            <thead>
              <tr className={isDark ? 'bg-[#1a1d28]' : 'bg-gray-50'}>
                {['#', '板块', '涨跌幅', '最新价', '换手率', '上涨', '下跌', '领涨股', '领涨%'].map(h => (
                  <th key={h} className={`px-3 py-2 text-right font-medium ${h === '板块' ? 'text-left' : ''} ${
                    isDark ? 'text-[#8892a4]' : 'text-gray-500'
                  }`}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={9} className={`text-center py-10 text-sm ${isDark ? 'text-[#5a6275]' : 'text-gray-400'}`}>
                    无匹配结果
                  </td>
                </tr>
              ) : filtered.map((s, i) => {
                const chg = s.change_pct ?? 0
                const lchg = s.lead_change ?? 0
                return (
                  <tr key={s.code} className={`${bg(i)} ${isDark ? 'hover:bg-amber-500/8' : 'hover:bg-amber-50'} transition-colors`}>
                    <td className={`px-3 py-2 text-right font-mono ${isDark ? 'text-[#5a6275]' : 'text-gray-400'}`}>{s.rank}</td>
                    <td className={`px-3 py-2 text-sm font-medium ${isDark ? 'text-[#e8edf5]' : 'text-gray-900'}`}>{s.name}</td>
                    <td className={`px-3 py-2 text-right font-mono font-medium ${
                      chg > 0 ? 'text-green-500' : chg < 0 ? 'text-red-500' : (isDark ? 'text-[#e8edf5]' : 'text-gray-900')
                    }`}>{chg > 0 ? '+' : ''}{chg.toFixed(2)}%</td>
                    <td className={`px-3 py-2 text-right font-mono ${isDark ? 'text-[#e8edf5]' : 'text-gray-900'}`}>{s.price?.toFixed(2) ?? '—'}</td>
                    <td className={`px-3 py-2 text-right font-mono ${isDark ? 'text-[#e8edf5]' : 'text-gray-900'}`}>{s.turnover?.toFixed(2) ?? '—'}</td>
                    <td className="px-3 py-2 text-right font-mono text-green-500">{s.up_count ?? '—'}</td>
                    <td className="px-3 py-2 text-right font-mono text-red-500">{s.down_count ?? '—'}</td>
                    <td className={`px-3 py-2 ${isDark ? 'text-[#8892a4]' : 'text-gray-500'}`}>{s.lead_stock || '—'}</td>
                    <td className={`px-3 py-2 text-right font-mono ${lchg > 0 ? 'text-green-500' : lchg < 0 ? 'text-red-500' : ''}`}>
                      {s.lead_stock ? (lchg > 0 ? '+' : '') + lchg.toFixed(2) + '%' : '—'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
