import { useEffect, useState } from 'react'
import { useThemeStore } from '../stores/themeStore'
import { api } from '../api/client'

interface Props { onSelect: (code: string) => void }

export default function Companies({ onSelect }: Props) {
  const { theme } = useThemeStore()
  const isDark = theme === 'dark'

  const [showHK, setShowHK] = useState(false)
  const [keyword, setKeyword] = useState('')
  const [page, setPage] = useState(1)
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  const fetchCompanies = async () => {
    setLoading(true)
    try {
      const exchange = showHK ? 'HK' : 'A'
      const kw = keyword ? `&keyword=${encodeURIComponent(keyword)}` : ''
      const res = await fetch(`/api/companies?exchange=${exchange}&page=${page}&page_size=20${kw}`)
      if (res.ok) setData(await res.json())
    } catch {}
    setLoading(false)
  }

  useEffect(() => { fetchCompanies() }, [page, showHK])
  useEffect(() => { setPage(1) }, [keyword, showHK])

  const totalPages = Math.ceil((data?.total || 0) / 20)

  return (
    <div>
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <h2 className="text-base font-semibold">公司档案库</h2>
        {/* A/HK 切换 */}
        <div className="flex rounded-md border overflow-hidden" style={{ borderColor: isDark ? '#1e2235' : '#d1d5db' }}>
          <button onClick={() => setShowHK(false)}
            className={`px-3 py-1 text-xs font-medium transition-colors ${
              !showHK
                ? (isDark ? 'bg-amber-500/20 text-amber-400' : 'bg-amber-50 text-amber-600')
                : (isDark ? 'text-[#8892a4] hover:text-white' : 'text-gray-500 hover:text-gray-900')
            }`}>A 股</button>
          <button onClick={() => setShowHK(true)}
            className={`px-3 py-1 text-xs font-medium transition-colors ${
              showHK
                ? (isDark ? 'bg-amber-500/20 text-amber-400' : 'bg-amber-50 text-amber-600')
                : (isDark ? 'text-[#8892a4] hover:text-white' : 'text-gray-500 hover:text-gray-900')
            }`}>港 股</button>
        </div>
        <input
          value={keyword}
          onChange={e => setKeyword(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && fetchCompanies()}
          placeholder="搜索公司名称..."
          className={`flex-1 max-w-xs px-3 py-1.5 text-sm rounded-md border outline-none ${isDark ? 'bg-[#1a1d28] border-[#1e2235] text-white placeholder-[#5a6275]' : 'bg-white border-gray-200 text-gray-800 placeholder-gray-400'}`}
        />
        <button onClick={fetchCompanies} className={`px-3 py-1.5 text-xs rounded-md border cursor-pointer ${isDark ? 'bg-[#1a1d28] border-[#1e2235] text-[#8892a4]' : 'bg-gray-100 border-gray-200 text-gray-500'}`}>搜索</button>
        {data && <span className={`text-xs ${isDark ? 'text-[#5a6275]' : 'text-gray-400'}`}>共 {data.total} 条</span>}
      </div>

      {loading ? (
        <div className="text-center py-16"><div className="w-8 h-8 border-3 border-t-amber-400 rounded-full animate-spin mx-auto" style={{borderColor:isDark?'#1e2235':'#d1d5db',borderTopColor:'#f5c842'}}/></div>
      ) : (
        <>
          <div className={`rounded-xl overflow-hidden border ${isDark ? 'bg-[#0f1117] border-[#1e2235]' : 'bg-white border-gray-200'}`}>
            <table className="w-full">
              <thead>
                <tr className={`text-left text-[11px] font-semibold uppercase tracking-wider ${isDark ? 'bg-[#1a1d28] text-[#5a6275]' : 'bg-gray-50 text-gray-500'}`}>
                  <th className="px-3.5 py-2.5">代码</th>
                  <th className="px-3.5 py-2.5">名称</th>
                  <th className="px-3.5 py-2.5">交易所</th>
                  <th className="px-3.5 py-2.5">行业</th>
                  <th className="px-3.5 py-2.5" colSpan={2}>操作</th>
                </tr>
              </thead>
              <tbody>
                {(data?.items || []).map((c: any) => (
                  <tr key={c.code} className={`border-b ${isDark ? 'border-[#1e2235]/50 hover:bg-purple-500/5' : 'border-gray-200 hover:bg-purple-50/50'}`}>
                    <td className={`px-3.5 py-2 text-xs font-mono ${isDark ? 'text-[#5a6275]' : 'text-gray-400'}`}>{c.code}</td>
                    <td className="px-3.5 py-2 text-sm font-medium">{c.name || '-'}</td>
                    <td className="px-3.5 py-2">
                      <span className={`inline-block px-2 py-0.5 rounded text-[11px] font-medium ${
                        c.exchange==='SZ'?'bg-blue-500/15 text-blue-500':c.exchange==='SH'?'bg-purple-500/15 text-purple-500':c.exchange==='HK'?'bg-amber-500/15 text-amber-500':''
                      }`}>{c.exchange}</span>
                    </td>
                    <td className={`px-3.5 py-2 text-sm ${isDark ? 'text-[#8892a4]' : 'text-gray-500'}`}>{c.industry || '-'}</td>
                    <td className="px-3.5 py-2">
                      <button onClick={() => onSelect(c.code)} className={`px-2.5 py-1 text-xs rounded-md border cursor-pointer ${isDark ? 'bg-[#1a1d28] border-[#1e2235] text-[#8892a4]' : 'bg-gray-100 border-gray-200 text-gray-500'} hover:opacity-80`}>财务</button>
                    </td>
                    <td className="px-3.5 py-2">
                      <button onClick={async () => {
                        try {
                          await fetch(`/api/collect/${c.code}`, {method:'POST'})
                        } catch {}
                      }} className={`px-2.5 py-1 text-xs rounded-md border cursor-pointer ${isDark ? 'bg-[#1a1d28] border-[#1e2235] text-amber-400' : 'bg-gray-100 border-gray-200 text-amber-600'} hover:opacity-80`}>采集</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2 mt-4">
              <button disabled={page<=1} onClick={()=>setPage(page-1)} className={`px-3 py-1 text-xs rounded-md border cursor-pointer disabled:opacity-30 ${isDark ? 'bg-[#1a1d28] border-[#1e2235] text-[#8892a4]' : 'bg-gray-100 border-gray-200 text-gray-500'}`}>上一页</button>
              <span className={`text-xs ${isDark ? 'text-[#5a6275]' : 'text-gray-400'}`}>{page}/{totalPages}</span>
              <button disabled={page>=totalPages} onClick={()=>setPage(page+1)} className={`px-3 py-1 text-xs rounded-md border cursor-pointer disabled:opacity-30 ${isDark ? 'bg-[#1a1d28] border-[#1e2235] text-[#8892a4]' : 'bg-gray-100 border-gray-200 text-gray-500'}`}>下一页</button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
