import type { Card } from '../types'

interface Props {
  slot: string
  card: Card
  chem: number
  isSelected: boolean
  onClick: () => void
}

const CHEM_COLOURS = ['text-red-400', 'text-yellow-400', 'text-yellow-300', 'text-chem']

export default function SlotCard({ slot, card, chem, isSelected, onClick }: Props) {
  return (
    <div
      data-slot={slot}
      onClick={onClick}
      className={`bg-card rounded px-2 py-1.5 text-center cursor-pointer select-none
        border transition-colors min-w-[52px]
        ${isSelected ? 'border-gold bg-navy' : 'border-border hover:border-muted'}`}
    >
      <div className="text-gold font-bold text-sm leading-none">{card.ovr}</div>
      <div className="text-white text-xs truncate max-w-[64px] mx-auto leading-tight mt-0.5">
        {card.player_name.split(' ').pop()}
      </div>
      <div className="text-muted text-[10px] leading-none">{slot}</div>
      <div className={`text-[10px] leading-none mt-0.5 ${CHEM_COLOURS[chem]}`}>
        {'●'.repeat(chem)}{'○'.repeat(3 - chem)}
      </div>
    </div>
  )
}
