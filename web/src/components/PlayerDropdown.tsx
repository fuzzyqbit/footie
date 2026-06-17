import { useState, useEffect, useRef } from 'react'
import type { Card } from '../types'

interface Props {
  slot: string
  cards: Card[]
  onSwap: (slot: string, cardId: string) => void
  onClose: () => void
}

export default function PlayerDropdown({ slot, cards, onSwap, onClose }: Props) {
  const [search, setSearch] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    inputRef.current?.focus()
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  const filtered = cards
    .filter(c =>
      c.player_name.toLowerCase().includes(search.toLowerCase()) ||
      c.id.includes(search.toLowerCase())
    )
    .slice(0, 20)

  return (
    <div className="absolute z-50 bg-card border border-gold rounded-lg shadow-xl w-64 mt-1">
      <div className="p-2 border-b border-border">
        <input
          ref={inputRef}
          type="text"
          placeholder="Search players..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="w-full bg-navy border border-border rounded px-2 py-1 text-sm text-fg placeholder-muted focus:outline-none focus:border-gold"
        />
      </div>
      <ul className="max-h-64 overflow-y-auto">
        {filtered.map(card => (
          <li key={card.id}>
            <button
              onClick={() => onSwap(slot, card.id)}
              className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-navy transition-colors"
            >
              <span className="text-gold font-bold text-sm w-6">{card.ovr}</span>
              <span className="flex-1 text-fg text-sm truncate">{card.player_name}</span>
              <span className="text-muted text-xs">{card.position}</span>
            </button>
          </li>
        ))}
        {filtered.length === 0 && (
          <li className="px-3 py-2 text-muted text-sm">No players found</li>
        )}
      </ul>
    </div>
  )
}
