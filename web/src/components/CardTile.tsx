import { useState } from 'react'
import type { Card } from '../types'
import { faceKeys } from '../faceLabels'
import { useIsWatched, toggleWatch } from '../watchlist'
import { statColor, tierColor } from '../statColor'
import { displayName } from '../displayName'
import StatRadar from './StatRadar'

interface Props {
  card: Card
}

function formatPrice(price: number | null): string {
  if (price == null) return '—'
  if (price >= 1_000_000) return `${(price / 1_000_000).toFixed(1)}M`
  if (price >= 1_000) return `${(price / 1_000).toFixed(0)}K`
  return String(price)
}

export default function CardTile({ card }: Props) {
  const [expanded, setExpanded] = useState(false)
  const watched = useIsWatched(card.id)
  const stats = faceKeys(card.position).map(
    ([key, label]) => [label, card.face[key]] as const,
  )

  return (
    <div
      className="bg-card rounded-lg p-3 cursor-pointer hover:bg-card-hover transition-colors border border-border"
      style={{ borderLeftColor: tierColor(card.ovr, card.version), borderLeftWidth: 3 }}
      onClick={() => setExpanded(e => !e)}
    >
      <div className="flex items-center gap-2 mb-1">
        <span className="text-gold font-bold text-lg w-8 text-center">{card.ovr}</span>
        <div className="flex-1 min-w-0">
          <div className="text-white font-medium truncate" title={card.player_name}>
            {displayName(card.player_name)}
          </div>
          <div className="flex items-center gap-1.5 text-xs min-w-0">
            <span className="text-muted shrink-0">{card.position}</span>
            <span
              className={
                'truncate rounded px-1.5 py-0.5 leading-none ' +
                (card.version.toLowerCase() === 'base'
                  ? 'bg-border text-muted'
                  : 'bg-gold/20 text-gold')
              }
              title={card.version}
            >
              {card.version}
            </span>
          </div>
        </div>
        <div className="text-chem text-sm font-medium">{formatPrice(card.price)}</div>
        <button
          type="button"
          aria-label={watched ? 'Remove from watchlist' : 'Add to watchlist'}
          aria-pressed={watched}
          onClick={e => {
            e.stopPropagation()
            toggleWatch(card)
          }}
          className={`shrink-0 text-lg leading-none transition-colors ${
            watched ? 'text-gold' : 'text-muted hover:text-white'
          }`}
        >
          {watched ? '★' : '☆'}
        </button>
      </div>

      {expanded && (
        <div className="mt-2 pt-2 border-t border-border flex items-center gap-3">
          <StatRadar values={stats.map(([, v]) => v)} />
          <div className="flex-1 flex flex-col gap-1">
            {stats.map(([label, v]) => (
              <div key={label} className="flex items-center gap-1.5 text-xs">
                <span className="text-muted w-7 shrink-0">{label}</span>
                <div className="flex-1 h-1.5 rounded bg-border overflow-hidden">
                  <div
                    className="h-full rounded"
                    style={{ width: `${v ?? 0}%`, backgroundColor: statColor(v) }}
                  />
                </div>
                <span className="text-white w-6 text-right">{v ?? '—'}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
