export type Theme = 'dark' | 'light'

const KEY = 'fc26-theme'

export function getTheme(): Theme {
  return document.documentElement.classList.contains('light') ? 'light' : 'dark'
}

export function applyTheme(theme: Theme): void {
  document.documentElement.classList.toggle('light', theme === 'light')
  try { localStorage.setItem(KEY, theme) } catch { /* storage may be unavailable */ }
}
