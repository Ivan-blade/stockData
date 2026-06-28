import { useEffect, useState, useMemo, useCallback } from 'react'
import { useThemeStore } from '../stores/themeStore'
import { useCompanyStore } from '../stores/companyStore'
import { api } from '../api/client'
import type { FinancialResponse } from '../types'
import ReactECharts from 'echarts-for-react'

const KEY_METRICS = [
  '营业总收入', '营业成本', '净利润', '归母净利润', '扣非净利润',
  '经营现金流量净额', '基本每股收益', '每股净资产', '每股经营现金流',
  '资产负债率', '毛利率', '销售净利率', '净资产收益率(ROE)',
]

/** 数值格式化：亿 / 万 / 原值 */
function fmtVal(v: number | null | undefined): string {
  if (v == null) return '—'
  const abs = Math.abs(v)
  if (abs >= 1e8) return (v / 1e8).toFixed(2) + '亿'
  if (abs >= 1e4) return (v / 1e4).toFixed(2) + '万'
  return v.toFixed(2)
}

/** 百分比格式化 */
function fmtPct(v: number | null): string {
  if (v == null) return '—'
  return (v >= 0 ? '+' : '') + v.toFixed(1) + '%'
}

/** 找到去年同期的日期 */
function samePeriodLastYear(dateStr: string): string | null {
  const parts = dateStr.split('-')
  if (parts.length !== 3) return null
  const y = Number(parts[0]) - 1
  return `${y}-${parts[1]}-${parts[2]}`
}

export default function Financial() {
  const { theme } = useThemeStore()
  const { cache, cacheLoaded, loadCache } = useCompanyStore()
  const [code, setCode] = useState('')
  const [data, setData] = useState<FinancialResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState('')
  const [selectedMetric, setSelectedMetric] = useState('营业总收入')
  const isDark = theme === 'dark'

  useEffect(() => {
    useCompanyStore.getState().loadCache().then(all => {
      if (all.length > 0 && !code) {
        const c = all[0]?.code
        setCode(c)
        if (c) fetchFinancial(c)
      }
    })
  }, [])

  const fetchFinancial = async (c: string) => {
    setLoading(true)
    try {
      setData(await api.companies.financial(c))
    } catch {
      setData(null)
    }
    setLoading(false)
  }

  const handleSelect = (c: string) => {
    setCode(c)
    setSelectedMetric('营业总收入')
    fetchFinancial(c)
  }

  const filtered = search
    ? cache.filter(c => c.name?.includes(search) || c.code.includes(search))
    : cache

  // 合并 summary + indicators
  const merged = useMemo(() => {
    if (!data) return {}
    const allKeys = new Set([...Object.keys(data.summary), ...Object.keys(data.indicators)])
    const result: Record<string, Record<string, number>> = {}
    for (const d of allKeys) {
      result[d] = { ...data.summary[d], ...data.indicators[d] }
    }
    return result
  }, [data])

  const dates = useMemo(() => Object.keys(merged).sort().reverse(), [merged])

  // 计算同比
  const getYoY = useCallback((metric: string, curDate: string): number | null => {
    const lastYear = samePeriodLastYear(curDate)
    if (!lastYear) return null
    const cur = merged[curDate]?.[metric]
    const prev = merged[lastYear]?.[metric]
    if (cur == null || prev == null || prev === 0) return null
    return (cur - prev) / Math.abs(prev) * 100
  }, [merged])

  // 趋势图配置
  const chartOpts = useMemo(() => {
    const ascDates = [...dates].reverse()
    const pts: [string, number][] = []
    for (const d of ascDates) {
      const v = merged[d]?.[selectedMetric]
      if (v != null) pts.push([d.slice(0, 7), v])
    }
    return {
      tooltip: {
        trigger: 'axis' as const,
        valueFormatter: (v: number) => fmtVal(v),
      },
      grid: { left: 60, right: 24, top: 40, bottom: 28 },
      xAxis: {
        type: 'category' as const,
        data: pts.map(p => p[0]),
        axisLabel: {
          color: isDark ? '#8892a4' : '#6b7280',
          fontSize: 11,
        },
        axisLine: { lineStyle: { color: isDark ? '#1e2235' : '#e5e7eb' } },
      },
      yAxis: {
        type: 'value' as const,
        axisLabel: {
          color: isDark ? '#8892a4' : '#6b7280',
          fontSize: 11,
          formatter: (v: number) => {
            if (Math.abs(v) >= 1e8) return (v / 1e8).toFixed(0) + '亿'
            if (Math.abs(v) >= 1e4) return (v / 1e4).toFixed(0) + '万'
            return String(v)
          },
        },
        splitLine: {
          lineStyle: {
            color: isDark ? '#1e2235' : '#e5e7eb',
            type: 'dashed' as const,
          },
        },
      },
      series: [{
        type: 'line' as const,
        data: pts.map(p => p[1]),
        smooth: true,
        lineStyle: { width: 2, color: '#f5c842' },
        itemStyle: { color: '#f5c842' },
        areaStyle: {
          color: {
            type: 'linear' as const,
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: isDark ? 'rgba(245,200,66,0.25)' : 'rgba(245,200,66,0.12)' },
              { offset: 1, color: isDark ? 'rgba(245,200,66,0.02)' : 'rgba(245,200,66,0.02)' },
            ],
          },
        },
        symbol: 'circle' as const,
        symbolSize: 6,
      }],
    }
  }, [dates, merged, selectedMetric, isDark])

  const currentCompany = cache.find(c => c.code === code)
  if (!isDark) {
    /* passes through */
  }

  return (
    <div>
      {/* ── 头部：标题 + 选择器 ── */}
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <h2 className="text-base font-semibold">财务数据</h2>
        <div className="relative" style={{ width: 280 }}>
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="搜索股票代码或名称..."
            className={`w-full px-3 py-1.5 pr-8 text-sm rounded-md border outline-none ${
              isDark
                ? 'bg-[#1a1d28] border-[#1e2235] text-white placeholder-[#5a6275]'
                : 'bg-white border-gray-200 text-gray-800 placeholder-gray-400'
            }`}
          />
          {search && (
            <div className={`absolute top-full left-0 right-0 mt-1 max-h-48 overflow-y-auto rounded-md border z-50 ${
              isDark ? 'bg-[#1a1d28] border-[#1e2235]' : 'bg-white border-gray-200'
            }`}>
              {filtered.slice(0, 10).map(c => (
                <div
                  key={c.code}
                  onClick={() => { setSearch(''); handleSelect(c.code) }}
                  className={`px-3 py-2 text-sm cursor-pointer ${
                    c.code === code ? (isDark ? 'bg-purple-500/20' : 'bg-purple-50') : ''
                  } ${isDark ? 'hover:bg-[#0f1117]' : 'hover:bg-gray-50'}`}
                >
                  <span className={`text-xs font-mono ${isDark ? 'text-[#5a6275]' : 'text-gray-400'}`}>{c.code}</span>{' '}
                  <span className="font-medium">{c.name}</span>
                  <span className={`text-xs ml-2 ${isDark ? 'text-[#5a6275]' : 'text-gray-400'}`}>{c.exchange}</span>
                </div>
              ))}
              {filtered.length === 0 && (
                <div className={`px-3 py-2 text-xs ${isDark ? 'text-[#5a6275]' : 'text-gray-400'}`}>无匹配</div>
              )}
            </div>
          )}
        </div>
      </div>

      {loading ? (
        <div className="text-center py-16">
          <div className="w-8 h-8 border-3 border-t-amber-400 rounded-full animate-spin mx-auto"
            style={{ borderColor: isDark ? '#1e2235' : '#d1d5db', borderTopColor: '#f5c842' }}
          />
        </div>
      ) : data ? (
        <>
          {/* ── 公司信息 ── */}
          <div className="flex items-center gap-2 mb-3">
            {currentCompany && (
              <span className="font-semibold text-sm">{currentCompany.name}（{code}）</span>
            )}
            <span className={`text-xs ${isDark ? 'text-[#5a6275]' : 'text-gray-400'}`}>
              共 {dates.length} 期
            </span>
          </div>

          {/* ── 数据表格 ── */}
          <div className="overflow-x-auto rounded-lg border" style={{
            borderColor: isDark ? '#1e2235' : '#e5e7eb',
          }}>
            <table className="w-full text-xs whitespace-nowrap">
              {/* 表头 */}
              <thead>
                <tr className={isDark ? 'bg-[#1a1d28]' : 'bg-gray-50'}>
                  <th className={`sticky left-0 z-10 px-3 py-2 text-left font-semibold text-sm ${
                    isDark ? 'bg-[#1a1d28] text-[#e8edf5]' : 'bg-gray-50 text-gray-900'
                  }`} style={{ minWidth: 120 }}>
                    指标
                  </th>
                  {dates.map(d => (
                    <th key={d} className={`px-3 py-2 text-right font-medium ${
                      isDark ? 'text-[#8892a4]' : 'text-gray-500'
                    }`} style={{ minWidth: 120 }}>
                      <span className="text-[11px]">{d.slice(0, 7)}</span>
                      <br />
                      <span className="text-[10px] opacity-60">{(d => {
                        const m = Number(d.slice(5, 7))
                        if (m <= 3) return 'Q1'
                        if (m <= 6) return 'Q2'
                        if (m <= 9) return 'Q3'
                        return 'Q4'
                      })(d)}</span>
                    </th>
                  ))}
                  <th className={`px-3 py-2 text-right font-medium ${
                    isDark ? 'text-[#8892a4]' : 'text-gray-500'
                  }`} style={{ minWidth: 90 }}>
                    同比变化
                  </th>
                </tr>
              </thead>
              {/* 表体 */}
              <tbody>
                {KEY_METRICS.map((metric, ri) => {
                  const latestVal = merged[dates[0]]?.[metric]
                  const yoy = getYoY(metric, dates[0])
                  const isSelected = selectedMetric === metric
                  const rowBg = isSelected
                    ? isDark ? 'bg-amber-500/8' : 'bg-amber-50'
                    : ri % 2 === 0
                      ? isDark ? 'bg-[#0f1117]/40' : 'bg-white'
                      : isDark ? 'bg-[#0f1117]/60' : 'bg-gray-50/60'

                  return (
                    <tr
                      key={metric}
                      onClick={() => setSelectedMetric(metric)}
                      className={`cursor-pointer transition-colors ${
                        isDark
                          ? `hover:bg-amber-500/12 ${rowBg}`
                          : `hover:bg-amber-50 ${rowBg}`
                      }`}
                    >
                      {/* 指标名称（粘性列） */}
                      <td className={`sticky left-0 z-10 px-3 py-2 text-sm font-medium ${
                        isDark
                          ? (isSelected ? 'text-amber-400' : 'text-[#e8edf5]')
                          : (isSelected ? 'text-amber-600' : 'text-gray-900')
                      } ${isDark ? 'bg-[#0f1117]' : 'bg-white'}`}
                        style={{ boxShadow: isDark ? '2px 0 4px rgba(0,0,0,0.3)' : '2px 0 4px rgba(0,0,0,0.06)' }}
                      >
                        {metric}
                        {isSelected && (
                          <span className="ml-1 text-[10px] opacity-60">📈</span>
                        )}
                      </td>
                      {/* 各期数值 */}
                      {dates.map(d => {
                        const v = merged[d]?.[metric]
                        return (
                          <td key={d} className={`px-3 py-2 text-right font-mono ${
                            v == null
                              ? isDark ? 'text-[#3a4260]' : 'text-gray-300'
                              : v > 0 ? 'text-green-500' : v < 0 ? 'text-red-500' : (isDark ? 'text-[#e8edf5]' : 'text-gray-900')
                          }`}>
                            {fmtVal(v)}
                          </td>
                        )
                      })}
                      {/* 同比 */}
                      <td className={`px-3 py-2 text-right font-mono font-medium ${
                        yoy == null
                          ? isDark ? 'text-[#3a4260]' : 'text-gray-300'
                          : yoy > 0 ? 'text-green-500' : 'text-red-500'
                      }`}>
                        {fmtPct(yoy)}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {/* ── 趋势图 ── */}
          <div className="mt-5">
            <div className="flex items-center gap-2 mb-2">
              <span className={`text-sm font-semibold ${isDark ? 'text-[#e8edf5]' : 'text-gray-900'}`}>
                趋势图
              </span>
              <span className={`text-xs font-medium ${isDark ? 'text-amber-400' : 'text-amber-600'}`}>
                {selectedMetric}
              </span>
              <span className={`text-[11px] ${isDark ? 'text-[#5a6275]' : 'text-gray-400'}`}>
                — 点击表格行切换
              </span>
            </div>
            <div className={`rounded-lg border ${isDark ? 'bg-[#0f1117] border-[#1e2235]' : 'bg-white border-gray-200'}`}>
              <ReactECharts option={chartOpts} style={{ height: 280 }} />
            </div>
          </div>
        </>
      ) : (
        <div className="text-center py-16 text-sm" style={{ color: isDark ? '#5a6275' : '#9ca3af' }}>
          选择公司查看财务数据
        </div>
      )}
    </div>
  )
}
