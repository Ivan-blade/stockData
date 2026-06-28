import { useEffect, useState } from 'react'
import { useThemeStore } from '../stores/themeStore'
import { useCompanyStore } from '../stores/companyStore'

interface Props { onSelect: () => void }

export default function Companies({ onSelect }: Props) {
  const { theme } = useThemeStore()
  const { companies, total, page, keyword, loading, load, setKeyword, setPage } = useCompanyStore()
  const [searchInput, setSearchInput] = useState('')
  const [collecting, setCollecting] = useState<string | null>(null)
  const isDark = theme === 'dark'
  const t = (d:string) => isDark ? d : d.replace('bg-[#0f1117]','bg-white').replace('border-[#1e2235]','border-gray-200').replace('bg-[#1a1d28]','bg-gray-100').replace('text-[#5a6275]','text-gray-400').replace('text-[#8892a4]','text-gray-500').replace('hover:bg-purple-500/5','hover:bg-purple-50/50')

  useEffect(() => { if (companies.length === 0) load() }, [])

  const handleCollect = async (code: string) => {
    setCollecting(code)
    await api.collect.one(code)
    setCollecting(null)
  }

  const totalPages = Math.ceil(total / 20)

  return (
    <div>
      <div className="flex items-center gap-3 mb-4">
        <h2 className="text-base font-semibold">公司档案库</h2>
        <input
          value={searchInput}
          onChange={e => setSearchInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && (setKeyword(searchInput), load(searchInput))}
          placeholder="搜索公司名称..."
          className={`flex-1 max-w-xs px-3 py-1.5 text-sm rounded-md border outline-none ${isDark ? 'bg-[#1a1d28] border-[#1e2235] text-white placeholder-[#5a6275]' : 'bg-white border-gray-200 text-gray-800 placeholder-gray-400'}`}
        />
        <button onClick={() => { setKeyword(searchInput); load(searchInput) }} className={`px-3 py-1.5 text-xs rounded-md border cursor-pointer ${isDark ? 'bg-[#1a1d28] border-[#1e2235] text-[#8892a4]' : 'bg-gray-100 border-gray-200 text-gray-500'}`}>搜索</button>
        <span className={`text-xs ${t('text-[#5a6275]')}`}>{total} 条</span>
      </div>

      {loading ? (
        <div className="text-center py-16"><div className="w-8 h-8 border-3 border-t-amber-400 rounded-full animate-spin mx-auto" style={{borderColor:isDark?'#1e2235':'#d1d5db',borderTopColor:'#f5c842'}}/></div>
      ) : (
        <>
          <div className={`rounded-xl overflow-hidden border ${t('bg-[#0f1117] border-[#1e2235]')}`}>
            <table className="w-full">
              <thead>
                <tr className={`text-left text-[11px] font-semibold uppercase tracking-wider ${t('bg-[#1a1d28] text-[#5a6275]')}`}>
                  <th className="px-3.5 py-2.5">代码</th>
                  <th className="px-3.5 py-2.5">名称</th>
                  <th className="px-3.5 py-2.5">交易所</th>
                  <th className="px-3.5 py-2.5">行业</th>
                  <th className="px-3.5 py-2.5" colSpan={2}>操作</th>
                </tr>
              </thead>
              <tbody>
                {companies.map(c => (
                  <tr key={c.code} className={`border-b ${t('border-[#1e2235]/50 hover:bg-purple-500/5')}`}>
                    <td className={`px-3.5 py-2 text-xs font-mono ${t('text-[#5a6275]')}`}>{c.code}</td>
                    <td className="px-3.5 py-2 text-sm font-medium">{c.name || '-'}</td>
                    <td className="px-3.5 py-2">
                      <span className={`inline-block px-2 py-0.5 rounded text-[11px] font-medium ${
                        c.exchange==='SZ'?'bg-blue-500/15 text-blue-500':c.exchange==='SH'?'bg-purple-500/15 text-purple-500':'bg-amber-500/15 text-amber-500'
                      }`}>{c.exchange}</span>
                    </td>
                    <td className={`px-3.5 py-2 text-sm ${t('text-[#8892a4]')}`}>{c.industry || '-'}</td>
                    <td className="px-3.5 py-2">
                      <button onClick={onSelect} className={`px-3 py-1 text-xs rounded-md border cursor-pointer ${t('bg-[#1a1d28] border-[#1e2235] text-[#8892a4]')} hover:opacity-80`}>查看财务</button>
                    </td>
                    <td className="px-3.5 py-2">
                      <button onClick={() => handleCollect(c.code)} disabled={collecting === c.code} className={`px-3 py-1 text-xs rounded-md border cursor-pointer disabled:opacity-50 ${t('bg-[#1a1d28] border-[#1e2235] text-[#8892a4]')} hover:opacity-80`}>
                        {collecting === c.code ? '...' : '采集'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2 mt-4">
              <button disabled={page<=1} onClick={()=>setPage(page-1)} className={`px-3 py-1 text-xs rounded-md border cursor-pointer disabled:opacity-30 ${t('bg-[#1a1d28] border-[#1e2235] text-[#8892a4]')}`}>上一页</button>
              <span className={`text-xs ${t('text-[#5a6275]')}`}>{page}/{totalPages}</span>
              <button disabled={page>=totalPages} onClick={()=>setPage(page+1)} className={`px-3 py-1 text-xs rounded-md border cursor-pointer disabled:opacity-30 ${t('bg-[#1a1d28] border-[#1e2235] text-[#8892a4]')}`}>下一页</button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
