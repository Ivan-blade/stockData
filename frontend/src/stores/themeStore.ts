import { create } from 'zustand'

type Theme = 'dark' | 'light'

interface ThemeStore {
  theme: Theme
  toggle: () => void
}

const getInitial = (): Theme => {
  if (typeof window === 'undefined') return 'light'
  return (localStorage.getItem('qv_theme') as Theme) || 'light'
}

export const useThemeStore = create<ThemeStore>((set) => ({
  theme: getInitial(),
  toggle: () =>
    set((s) => {
      const next = s.theme === 'dark' ? 'light' : 'dark'
      localStorage.setItem('qv_theme', next)
      return { theme: next }
    }),
}))
