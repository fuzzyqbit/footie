import { useState } from 'react'
import { getTheme, applyTheme, type Theme } from '../theme'

export default function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(getTheme())
  const next: Theme = theme === 'dark' ? 'light' : 'dark'
  return (
    <button
      type="button"
      onClick={() => { applyTheme(next); setTheme(next) }}
      aria-label={`Switch to ${next} mode`}
      className="mt-auto flex items-center gap-2 px-3 py-2 rounded text-sm font-medium text-muted hover:text-fg hover:bg-navy transition-colors"
    >
      <span aria-hidden>{theme === 'dark' ? '\u2600' : '\u263e'}</span>
      <span>{theme === 'dark' ? 'Light' : 'Dark'} mode</span>
    </button>
  )
}
