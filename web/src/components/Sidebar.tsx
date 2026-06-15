import { NavLink } from 'react-router-dom'
import { useWatchlist } from '../watchlist'

const LINKS = [
  { to: '/cards', label: 'Cards' },
  { to: '/squads', label: 'Squads' },
  { to: '/build', label: 'Build' },
  { to: '/upgrade', label: 'Upgrade' },
  { to: '/updates', label: 'Latest' },
  { to: '/value', label: 'Value' },
  { to: '/watchlist', label: 'Flagged' },
  { to: '/compare', label: 'Compare' },
  { to: '/objectives', label: 'Objectives' },
  { to: '/sbcs', label: 'SBCs' },
]

export default function Sidebar() {
  const watchCount = useWatchlist().length
  return (
    <nav className="w-40 flex-shrink-0 bg-card border-r border-border flex flex-col py-6 px-3 gap-1">
      <div className="text-gold font-bold text-lg px-3 mb-6">FC 26</div>
      {LINKS.map(({ to, label }) => (
        <NavLink
          key={to}
          to={to}
          className={({ isActive }) =>
            `flex items-center justify-between px-3 py-2 rounded text-sm font-medium transition-colors ${
              isActive
                ? 'text-gold bg-navy border-l-2 border-gold'
                : 'text-muted hover:text-white hover:bg-navy'
            }`
          }
        >
          <span>{label}</span>
          {to === '/watchlist' && watchCount > 0 && (
            <span className="bg-gold/20 text-gold rounded-full px-1.5 py-0.5 text-xs leading-none">
              {watchCount}
            </span>
          )}
        </NavLink>
      ))}
    </nav>
  )
}
