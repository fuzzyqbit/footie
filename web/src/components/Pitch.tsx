import type { Card, ChemReport } from '../types'
import SlotCard from './SlotCard'

interface Props {
  formationSlots: string[]
  slotCards: Record<string, Card>
  chemReport: ChemReport | null
  selectedSlot: string | null
  onSlotClick: (slot: string) => void
}

function slotRow(slot: string): number {
  if (slot === 'GK') return 0
  if (/^(RB|CB|LB)/.test(slot)) return 1
  if (/^(CDM|DM)/.test(slot)) return 2
  if (/^(CM|RM|LM)/.test(slot)) return 3
  if (/^(CAM|RW|LW|AM)/.test(slot)) return 4
  if (/^(ST|CF|SS)/.test(slot)) return 5
  return 3
}

export default function Pitch({ formationSlots, slotCards, chemReport, selectedSlot, onSlotClick }: Props) {
  const chemBySlot: Record<string, number> = {}
  for (const p of chemReport?.players ?? []) chemBySlot[p.slot] = p.chem

  const rows = new Map<number, string[]>()
  for (const slot of formationSlots) {
    const r = slotRow(slot)
    if (!rows.has(r)) rows.set(r, [])
    rows.get(r)!.push(slot)
  }
  const sortedRows = [...rows.entries()].sort((a, b) => b[0] - a[0])

  return (
    <div className="bg-pitch rounded-lg p-4 flex flex-col items-center justify-around gap-3 min-h-[360px]
      border border-[rgba(255,255,255,0.1)] relative">
      {sortedRows.map(([rowNum, slots]) => (
        <div key={rowNum} className="flex gap-2 justify-center">
          {slots.map(slot => {
            const card = slotCards[slot]
            if (!card) return null
            return (
              <SlotCard
                key={slot}
                slot={slot}
                card={card}
                chem={chemBySlot[slot] ?? 0}
                isSelected={selectedSlot === slot}
                onClick={() => onSlotClick(slot)}
              />
            )
          })}
        </div>
      ))}
    </div>
  )
}
