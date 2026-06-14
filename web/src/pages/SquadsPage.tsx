import { useState, useEffect } from 'react'
import { useSquads, useSquad, useSaveSquad } from '../api/squads'
import { useChem } from '../api/chem'
import { useAllCards } from '../api/cards'
import { useMeta } from '../api/meta'
import Pitch from '../components/Pitch'
import SidePanel from '../components/SidePanel'
import PlayerDropdown from '../components/PlayerDropdown'
import SkeletonPitch from '../components/SkeletonPitch'
import type { Card, ChemReport, SquadFile } from '../types'

function slotId(value: SquadFile['starting_xi'][string]): string {
  return typeof value === 'string' ? value : value.id
}

export default function SquadsPage() {
  const { data: squadList } = useSquads()
  const { data: meta } = useMeta()
  const { data: allCardsData } = useAllCards()
  const allCards = allCardsData?.cards ?? []

  const [selectedSquadName, setSelectedSquadName] = useState<string | null>(null)
  const { data: loadedSquad, isPending: squadLoading } = useSquad(selectedSquadName)

  const [editedSquad, setEditedSquad] = useState<SquadFile | null>(null)
  const [chemReport, setChemReport] = useState<ChemReport | null>(null)
  const [selectedSlot, setSelectedSlot] = useState<string | null>(null)
  const [dropdownSlot, setDropdownSlot] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saveSuccess, setSaveSuccess] = useState(false)

  const chemMutation = useChem()
  const saveMutation = useSaveSquad()

  // Compute chemistry as soon as a squad loads so the pitch and side panel show
  // live chem immediately — not only after the user swaps a player.
  useEffect(() => {
    if (!loadedSquad) return
    let active = true
    chemMutation
      .mutateAsync(loadedSquad)
      .then(report => { if (active) setChemReport(report) })
      .catch(() => {})
    return () => { active = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loadedSquad])

  const squad = editedSquad ?? loadedSquad ?? null

  const cardById: Record<string, Card> = {}
  for (const c of allCards) cardById[c.id] = c

  const slotCards: Record<string, Card> = {}
  if (squad) {
    for (const [slot, val] of Object.entries(squad.starting_xi)) {
      const id = slotId(val)
      if (cardById[id]) slotCards[slot] = cardById[id]
    }
  }

  const formationSlots = squad ? (meta?.formations[squad.formation] ?? []) : []

  function handleSelectSquad(name: string) {
    setSelectedSquadName(name)
    setEditedSquad(null)
    setChemReport(null)
    setSelectedSlot(null)
  }

  function handleSlotClick(slot: string) {
    setSelectedSlot(slot)
    setDropdownSlot(slot)
  }

  async function handleSwap(slot: string, cardId: string) {
    if (!squad) return
    setDropdownSlot(null)
    const prevSquad = squad
    const newSquad: SquadFile = {
      ...squad,
      starting_xi: { ...squad.starting_xi, [slot]: cardId },
    }
    setEditedSquad(newSquad)
    try {
      const report = await chemMutation.mutateAsync(newSquad)
      setChemReport(report)
    } catch {
      setEditedSquad(prevSquad)
    }
  }

  async function handleSave() {
    if (!squad || !selectedSquadName) return
    setSaveError(null)
    setSaveSuccess(false)
    try {
      await saveMutation.mutateAsync({ name: selectedSquadName, squad })
      setSaveSuccess(true)
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : 'Save failed')
    }
  }

  const selectedCard = selectedSlot ? (slotCards[selectedSlot] ?? null) : null

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-4">Squads</h1>
      <div className="flex gap-4">
        <div className="w-44 flex-shrink-0">
          <div className="text-muted text-xs uppercase tracking-wider mb-2">Saved squads</div>
          {!squadList?.length && (
            <div className="text-muted text-sm">No squads saved yet</div>
          )}
          {squadList?.map(s => (
            <button
              key={s.name}
              onClick={() => handleSelectSquad(s.name)}
              className={`w-full text-left px-3 py-2 rounded text-sm mb-1 transition-colors
                ${selectedSquadName === s.name
                  ? 'bg-gold text-navy font-medium'
                  : 'bg-card text-white hover:bg-card-hover'}`}
            >
              {s.name}
            </button>
          ))}
        </div>

        {squad && (
          <div className="flex gap-4 flex-1 relative">
            <div className="flex-1 relative">
              {squadLoading ? (
                <SkeletonPitch />
              ) : (
                <Pitch
                  formationSlots={formationSlots}
                  slotCards={slotCards}
                  chemReport={chemReport}
                  selectedSlot={selectedSlot}
                  onSlotClick={handleSlotClick}
                />
              )}

              {dropdownSlot && (
                <div className="absolute top-2 left-1/2 -translate-x-1/2">
                  <PlayerDropdown
                    slot={dropdownSlot}
                    cards={allCards}
                    onSwap={handleSwap}
                    onClose={() => setDropdownSlot(null)}
                  />
                </div>
              )}

              <div className="mt-3 flex items-center gap-3">
                <button
                  onClick={handleSave}
                  disabled={saveMutation.isPending}
                  className="px-4 py-2 bg-gold text-navy font-medium rounded text-sm disabled:opacity-50"
                >
                  {saveMutation.isPending ? 'Saving…' : 'Save'}
                </button>
                {saveSuccess && <span className="text-chem text-sm">Saved</span>}
                {saveError && <span className="text-red-400 text-sm">{saveError}</span>}
              </div>
            </div>

            <SidePanel slot={selectedSlot} card={selectedCard} chemReport={chemReport} />
          </div>
        )}

        {!squad && !selectedSquadName && (
          <div className="flex-1 flex items-center justify-center text-muted">
            Select a squad to view
          </div>
        )}
      </div>
    </div>
  )
}
