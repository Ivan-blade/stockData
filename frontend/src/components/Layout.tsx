import { type ReactNode } from 'react'
import { useThemeStore } from '../stores/themeStore'

const tabs = [
  { key: 'dashboard', label: '概览' },
  { key: 'companies', label: '公司库' },
  { key: 'financial', label: '基本面' },
]

interface LayoutProps {
  activeTab: string
  onTabChange: (key: string) => void
  children: ReactNode
}

export default function Layout({ activeTab, onTabChange, children }: LayoutProps) {
  const { theme, toggle } = useThemeStore()
  const isDark = theme === 'dark'

  return (
    <div className={`min-h-screen ${isDark ? 'bg-[#07080a] text-[#e8eaed]' : 'bg-[#f5f6f8] text-[#1a1d2e]'}`}>
      {/* Grid background */}
      {isDark && (
        <div
          className="fixed inset-0 pointer-events-none z-0"
          style={{
            backgroundImage:
              'linear-gradient(rgba(30,34,53,.3) 1px, transparent 1px), linear-gradient(90deg, rgba(30,34,53,.3) 1px, transparent 1px)',
            backgroundSize: '40px 40px',
          }}
        />
      )}

      {/* Header */}
      <header
        className={`sticky top-0 z-50 px-8 border-b ${
          isDark
            ? 'bg-[#07080a] border-[#1e2235]'
            : 'bg-[#f5f6f8]/92 backdrop-blur border-gray-200'
        }`}
      >
        <div className="max-w-[1400px] mx-auto h-16 flex items-center gap-10">
          <h1 className="text-lg font-bold tracking-wider">
            <span className={`bg-gradient-to-r ${isDark ? 'from-[#e8eaed] to-[#f5c842]' : 'from-[#1a1d2e] to-[#c9a427]'} bg-clip-text text-transparent`}>
              QuickView
            </span>
            <span className={`text-xs ml-1 ${isDark ? 'text-[#5a6275]' : 'text-gray-400'}`}>· stockData</span>
          </h1>

          <nav className="flex items-stretch h-full gap-1">
            {tabs.map((t) => (
              <button
                key={t.key}
                onClick={() => onTabChange(t.key)}
                className={`px-5 text-sm font-medium tracking-wide transition-colors relative ${
                  activeTab === t.key
                    ? isDark ? 'text-[#f5c842]' : 'text-amber-600'
                    : isDark ? 'text-[#8892a4]' : 'text-gray-500'
                }`}
              >
                {t.label}
                {activeTab === t.key && (
                  <span className="absolute bottom-0 left-3 right-3 h-[2px] rounded-t bg-[#f5c842]" />
                )}
              </button>
            ))}
          </nav>

          <button
            onClick={toggle}
            className={`ml-auto px-3 py-1.5 text-sm rounded-md border cursor-pointer transition-colors ${
              isDark
                ? 'border-[#1e2235] text-[#8892a4] hover:text-[#e8eaed]'
                : 'border-gray-200 text-gray-500 hover:text-gray-800'
            }`}
          >
            {isDark ? '☀️ 白天' : '🌙 夜间'}
          </button>
        </div>
      </header>

      {/* Content */}
      <main className="relative z-10 max-w-[1400px] mx-auto px-8 py-6">{children}</main>
    </div>
  )
}
