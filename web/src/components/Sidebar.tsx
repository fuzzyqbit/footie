import { NavLink } from 'react-router-dom'

const LINKS = [
  { to: '/cards', label: 'Cards' },
  { to: '/squads', label: 'Squads' },
  { to: '/build', label: 'Build' },
  { to: '/upgrade', label: 'Upgrade' },
  { to: '/updates', label: 'Latest' },
]

export default function Sidebar() {
  return (
    <nav className="w-40 flex-shrink-0 bg-card border-r border-border flex flex-col py-6 px-3 gap-1">
      <div className="text-gold font-bold text-lg px-3 mb-6">FC 26</div>
      {LINKS.map(({ to, label }) => (
        <NavLink
          key={to}
          to={to}
          className={({ isActive }) =>
            `px-3 py-2 rounded text-sm font-medium transition-colors ${
              isActive
                ? 'text-gold bg-navy border-l-2 border-gold'
                : 'text-muted hover:text-white hover:bg-navy'
            }`
          }
        >
          {label}
        </NavLink>
      ))}
    </nav>
  )
}
