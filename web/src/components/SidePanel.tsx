import type { Card, ChemReport } from '../types'
import { faceKeys } from '../faceLabels'

interface Props {
  slot: string | null
  card: Card | null
  chemReport: ChemReport | null
}

function formatPrice(price: number | null): string {
  if (price == null) return '—'
  if (price >= 1_000_000) return `${(price / 1_000_000).toFixed(1)}M`
  if (price >= 1_000) return `${(price / 1_000).toFixed(0)}K`
  return String(price)
}

export default function SidePanel({ slot, card, chemReport }: Props) {
  if (!slot || !card) {
    return (
      <div className="w-52 flex-shrink-0 bg-card border border-border rounded-lg p-4 flex items-center justify-center text-muted text-sm text-center">
        Click a player to see details
      </div>
    )
  }

  const playerChem = chemReport?.players.find(p => p.slot === slot)
  const teamTotal = chemReport?.team_total ?? null

  return (
    <div className="w-52 flex-shrink-0 bg-card border border-border rounded-lg p-4 flex flex-col gap-3">
      <div>
        <div className="text-gold font-bold text-xl">{card.ovr}</div>
        <div className="text-white font-medium">{card.player_name}</div>
        <div className="text-muted text-sm">{card.position} · {card.version}</div>
      </div>

      <div className="text-xs text-muted space-y-0.5">
        {card.club && <div>{card.club}</div>}
        {card.nation && <div>{card.nation}</div>}
        {card.league && <div>{card.league}</div>}
        <div className="text-chem">{formatPrice(card.price)}</div>
      </div>

      <div className="grid grid-cols-2 gap-1.5">
        {faceKeys(card.position).map(([key, label]) => (
          <div key={key} className="flex justify-between text-xs bg-navy rounded px-2 py-1">
            <span className="text-muted">{label}</span>
            <span className="text-white font-medium">{card.face[key] ?? '—'}</span>
          </div>
        ))}
      </div>

      {playerChem != null && (
        <div className="space-y-1 pt-2 border-t border-border">
          <div className="flex justify-between text-xs">
            <span className="text-muted">Player chem</span>
            <span className="text-chem font-medium">{playerChem.chem}/3</span>
          </div>
          {teamTotal != null && (
            <div className="flex justify-between text-xs">
              <span className="text-muted">Team chem</span>
              <span className="text-chem font-medium">{teamTotal}/33</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
