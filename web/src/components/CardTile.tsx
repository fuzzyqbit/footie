import { useState } from 'react'
import type { Card } from '../types'
import { faceKeys } from '../faceLabels'

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

  return (
    <div
      className="bg-card rounded-lg p-3 cursor-pointer hover:bg-card-hover transition-colors border border-border"
      onClick={() => setExpanded(e => !e)}
    >
      <div className="flex items-center gap-2 mb-1">
        <span className="text-gold font-bold text-lg w-8 text-center">{card.ovr}</span>
        <div className="flex-1 min-w-0">
          <div className="text-white font-medium truncate">{card.player_name}</div>
          <div className="text-muted text-xs">{card.position}</div>
        </div>
        <div className="text-chem text-sm font-medium">{formatPrice(card.price)}</div>
      </div>

      {expanded && (
        <div className="mt-2 pt-2 border-t border-border grid grid-cols-3 gap-1">
          {faceKeys(card.position).map(([key, label]) => (
            <div key={key} className="flex justify-between text-xs">
              <span className="text-muted">{label}</span>
              <span className="text-white">{card.face[key] ?? '—'}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
