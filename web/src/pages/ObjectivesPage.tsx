import { useState } from 'react'
import { useCards } from '../api/cards'
import CardTile from '../components/CardTile'
import SkeletonGrid from '../components/SkeletonGrid'

const POSITIONS = ['GK', 'CB', 'RB', 'LB', 'CDM', 'CM', 'CAM', 'RM', 'LM', 'RW', 'LW', 'ST', 'CF']

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
      <h1 className="text-2xl font-bold text-white mb-1">Objectives &amp; SBCs</h1>
      <p className="text-muted text-sm mb-4">
        Non-tradeable cards — no market price. You earn these from objectives, SBCs or packs.
        Hit “How to get” on a card for the real requirements.
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
        <p className="text-muted text-sm">No non-tradeable cards match the filter.</p>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
          {cards.map(card => (
            <div key={card.id}>
              <CardTile card={card} />
              <div className="flex justify-between items-center text-xs mt-1 px-1">
                <span className="text-muted truncate" title={card.version}>{card.version}</span>
                {card.source_url ? (
                  <a
                    href={card.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-gold hover:underline shrink-0 ml-2"
                  >
                    How to get →
                  </a>
                ) : (
                  <span className="text-muted shrink-0 ml-2">see in-game</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
