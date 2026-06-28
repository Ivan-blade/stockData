import { useState } from 'react'
import { useThemeStore } from './stores/themeStore'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Companies from './pages/Companies'
import Financial from './pages/Financial'
import Sectors from './pages/Sectors'

export default function App() {
  const [tab, setTab] = useState('dashboard')
  const [selectedCode, setSelectedCode] = useState('')
  const { theme } = useThemeStore()
  const isDark = theme === 'dark'

  return (
    <Layout activeTab={tab} onTabChange={t => { setTab(t); if (t !== 'financial') setSelectedCode('') }}>
      {tab === 'dashboard' && <Dashboard />}
      {tab === 'companies' && <Companies onSelect={(code) => { setSelectedCode(code); setTab('financial') }} />}
      {tab === 'financial' && <Financial initialCode={selectedCode} />}
      {tab === 'sectors' && <Sectors />}
    </Layout>
  )
}
