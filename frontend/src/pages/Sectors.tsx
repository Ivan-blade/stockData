import { useEffect, useState, useMemo } from 'react'
import { useThemeStore } from '../stores/themeStore'
import ReactECharts from 'echarts-for-react'

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

interface HistoryItem {
  trade_date: string
  change_pct: number | null
  up_count: number | null
  down_count: number | null
  turnover: number | null
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

  // 单板块详情
  const [detailCode, setDetailCode] = useState<string | null>(null)
  const [detailName, setDetailName] = useState('')
  const [history, setHistory] = useState<HistoryItem[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)

  const fetchSectors = async () => {
    setLoading(true)
    try {
      const r = await fetch(`${API}/api/sectors?board_type=${tab}&sort_by=${sortBy}&limit=500`)
      if (r.ok) setData(await r.json())
    } catch {}
    setLoading(false)
  }

  useEffect(() => { fetchSectors() }, [tab, sortBy])

  const fetchHistory = async (code: string, name: string) => {
    setDetailCode(code)
    setDetailName(name)
    setHistoryLoading(true)
    try {
      const r = await fetch(`${API}/api/sectors/${code}/history?days=60`)
      if (r.ok) {
        const d = await r.json()
        setHistory(d.items ?? [])
      }
    } catch {}
    setHistoryLoading(false)
  }

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

  // 历史趋势图配置
  const chartOpts = useMemo(() => {
    const asc = [...history].reverse()
    const pts: [string, number][] = []
    for (const h of asc) {
      if (h.change_pct != null) {
        pts.push([h.trade_date.slice(5), h.change_pct])
      }
    }
    return {
      tooltip: {
        trigger: 'axis' as const,
        valueFormatter: (v: number) => v.toFixed(2) + '%',
      },
      grid: { left: 50, right: 20, top: 35, bottom: 25 },
      xAxis: {
        type: 'category' as const,
        data: pts.map(p => p[0]),
        axisLabel: { color: isDark ? '#8892a4' : '#6b7280', fontSize: 10 },
        axisLine: { lineStyle: { color: isDark ? '#1e2235' : '#e5e7eb' } },
      },
      yAxis: {
        type: 'value' as const,
        axisLabel: {
          color: isDark ? '#8892a4' : '#6b7280', fontSize: 10,
          formatter: (v: number) => v.toFixed(1) + '%',
        },
        splitLine: { lineStyle: { color: isDark ? '#1e2235' : '#e5e7eb', type: 'dashed' as const } },
      },
      series: [{
        type: 'line' as const,
        data: pts.map(p => p[1]),
        smooth: true,
        lineStyle: { width: 2, color: '#f5c842' },
        itemStyle: { color: '#f5c842' },
        areaStyle: {
          color: {
            type: 'linear' as const, x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: isDark ? 'rgba(245,200,66,0.25)' : 'rgba(245,200,66,0.12)' },
              { offset: 1, color: isDark ? 'rgba(245,200,66,0.02)' : 'rgba(245,200,66,0.02)' },
            ],
          },
        },
        symbol: 'circle' as const,
        symbolSize: 4,
      }],
    }
  }, [history, isDark])

  return (
    <div>
      {/* ── 头部 ── */}
      <div className="flex items-center gap-3 mb-3 flex-wrap">
        <h2 className="text-base font-semibold">板块排行</h2>
        <div className="flex rounded-md border overflow-hidden" style={{ borderColor: isDark ? '#1e2235' : '#d1d5db' }}>
          {(['industry', 'concept'] as const).map(t => (
            <button key={t}
              onClick={() => { setTab(t); setSearch(''); setDetailCode(null) }}
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
        <span className={`text-xs self-center ml-2 ${isDark ? 'text-[#5a6275]' : 'text-gray-400'}`}>
          点击板块名称查看历史走势
        </span>
      </div>

      <div className="flex gap-3">
        {/* ── 左侧：表格 ── */}
        <div className={`flex-1 overflow-x-auto rounded-lg border min-w-0 ${
          detailCode ? '' : ''
        }`} style={{ borderColor: isDark ? '#1e2235' : '#e5e7eb' }}>
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
              {loading ? (
                <tr>
                  <td colSpan={9} className="text-center py-16">
                    <div className="w-6 h-6 border-2 border-t-amber-400 rounded-full animate-spin mx-auto"
                      style={{ borderColor: isDark ? '#1e2235' : '#d1d5db', borderTopColor: '#f5c842' }}
                    />
                  </td>
                </tr>
              ) : filtered.length === 0 ? (
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
                    <td className={`px-3 py-2 text-sm font-medium cursor-pointer ${
                      detailCode === s.code
                        ? 'text-amber-400'
                        : isDark ? 'text-[#e8edf5] hover:text-amber-400' : 'text-gray-900 hover:text-amber-600'
                    }`}
                      onClick={() => fetchHistory(s.code, s.name)}>
                      {s.name}
                      {detailCode === s.code && <span className="ml-1 text-[10px]">📊</span>}
                    </td>
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

        {/* ── 右侧：详情面板 ── */}
        {detailCode && (
          <div className="w-80 shrink-0" style={{ maxHeight: '70vh', overflow: 'hidden' }}>
            <div className={`rounded-lg border h-full flex flex-col ${isDark ? 'bg-[#0f1117] border-[#1e2235]' : 'bg-white border-gray-200'}`}>
              {/* 标题 */}
              <div className={`flex items-center justify-between px-4 py-2.5 border-b ${isDark ? 'border-[#1e2235]' : 'border-gray-200'}`}>
                <div>
                  <span className="font-semibold text-sm">{detailName}</span>
                  <button onClick={() => setDetailCode(null)}
                    className={`ml-2 text-xs px-1.5 py-0.5 rounded ${isDark ? 'hover:bg-[#1a1d28] text-[#5a6275]' : 'hover:bg-gray-100 text-gray-400'}`}>
                    ✕
                  </button>
                </div>
              </div>
              {/* 图表 */}
              <div className="flex-1 overflow-hidden">
                {historyLoading ? (
                  <div className="flex items-center justify-center h-full py-16">
                    <div className="w-5 h-5 border-2 border-t-amber-400 rounded-full animate-spin"
                      style={{ borderColor: isDark ? '#1e2235' : '#d1d5db', borderTopColor: '#f5c842' }}
                    />
                  </div>
                ) : history.length > 1 ? (
                  <ReactECharts option={chartOpts} style={{ height: '100%', minHeight: 250 }} />
                ) : (
                  <div className={`text-center py-16 text-xs ${isDark ? 'text-[#5a6275]' : 'text-gray-400'}`}>
                    暂无历史数据（需要多采集几天）
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
