import { useState } from 'react'
import { useCards } from '../api/cards'
import CardTile from '../components/CardTile'
import SkeletonGrid from '../components/SkeletonGrid'

const POSITIONS = ['GK', 'CB', 'RB', 'LB', 'CDM', 'CM', 'CAM', 'RM', 'LM', 'RW', 'LW', 'ST', 'CF']

// The data has no per-card acquisition info, only the card type (version).
// Map that type to the real in-game route(s) it comes from — generic but
// honest, rather than claiming a specific objective we don't have data for.
function acquisitionRoute(version: string): string {
  const v = version.toLowerCase()
  if (v.includes('sbc')) return 'Squad Building Challenge'
  if (v === 'totw' || v === 'sif') return 'Team of the Week — packs while live'
  if (v.includes('hero')) return 'Hero — SBC or packs'
  if (v.includes('icon')) return 'Icon — SBC or packs'
  if (v === 'base') return 'Untradeable / not on the market'
  return `${version} — promo (packs / SBC / objective, varies)`
}

export default function ObjectivesPage() {
  const [pos, setPos] = useState('')
  const { data, isPending, error } = useCards({
    no_price: true,
    pos: pos || undefined,
    sort: 'ovr',
    limit: 1000,
  })
  const cards = data?.cards ?? []

  const inputCls =
    'bg-card border border-border rounded px-2 py-1.5 text-sm text-white focus:outline-none focus:border-gold'

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-1">Untradeable</h1>
      <p className="text-muted text-sm mb-4">
        Cards with no market price — you earn these in-game (packs, SBCs, objectives), they
        can’t be bought. The card type below is the route; exact requirements vary by card.
      </p>

      <div className="flex flex-wrap gap-3 mb-4">
        <select aria-label="Position" value={pos} onChange={e => setPos(e.target.value)} className={inputCls}>
          <option value="">All positions</option>
          {POSITIONS.map(p => <option key={p} value={p}>{p}</option>)}
        </select>
      </div>

      {error && (
        <div className="text-red-400 bg-red-900/20 border border-red-800 rounded p-3 mb-4">
          {error.message}
        </div>
      )}

      {data && <p className="text-muted text-sm mb-3">{cards.length} cards</p>}

      {isPending ? (
        <SkeletonGrid />
      ) : cards.length === 0 ? (
        <p className="text-muted text-sm">No untradeable cards match the filter.</p>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
          {cards.map(card => (
            <div key={card.id}>
              <CardTile card={card} />
              <div className="text-xs text-muted mt-1 px-1 truncate" title={acquisitionRoute(card.version)}>
                {acquisitionRoute(card.version)}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
