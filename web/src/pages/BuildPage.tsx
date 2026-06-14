import { useState } from 'react'
import { useBuild } from '../api/build'
import { useSaveSquad } from '../api/squads'
import { useChem } from '../api/chem'
import { useAllCards } from '../api/cards'
import { useMeta } from '../api/meta'
import Pitch from '../components/Pitch'
import SidePanel from '../components/SidePanel'
import PlayerDropdown from '../components/PlayerDropdown'
import type { Card, ChemReport, SquadFile } from '../types'

function slotId(value: SquadFile['starting_xi'][string]): string {
  return typeof value === 'string' ? value : value.id
}

export default function BuildPage() {
  const { data: meta } = useMeta()
  const { data: allCardsData } = useAllCards()
  const allCards = allCardsData?.cards ?? []

  const formations = Object.keys(meta?.formations ?? {})

  const [formation, setFormation] = useState('4-2-3-1')
  const [budget, setBudget] = useState('')
  const [league, setLeague] = useState('')
  const [buildError, setBuildError] = useState<string | null>(null)

  const [builtSquad, setBuiltSquad] = useState<SquadFile | null>(null)
  const [chemReport, setChemReport] = useState<ChemReport | null>(null)
  const [selectedSlot, setSelectedSlot] = useState<string | null>(null)
  const [dropdownSlot, setDropdownSlot] = useState<string | null>(null)

  const [squadName, setSquadName] = useState('built-squad')
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saveSuccess, setSaveSuccess] = useState(false)

  const buildMutation = useBuild()
  const chemMutation = useChem()
  const saveMutation = useSaveSquad()

  const cardById: Record<string, Card> = {}
  for (const c of allCards) cardById[c.id] = c

  const slotCards: Record<string, Card> = {}
  if (builtSquad) {
    for (const [slot, val] of Object.entries(builtSquad.starting_xi)) {
      const id = slotId(val)
      if (cardById[id]) slotCards[slot] = cardById[id]
    }
  }

  const formationSlots = builtSquad ? (meta?.formations[builtSquad.formation] ?? []) : []
  const selectedCard = selectedSlot ? (slotCards[selectedSlot] ?? null) : null

  async function handleBuild() {
    setBuildError(null)
    try {
      const result = await buildMutation.mutateAsync({
        formation,
        budget,
        league: league || undefined,
      })
      setBuiltSquad(result.squad)
      setChemReport(null)
      setSelectedSlot(null)
    } catch (e) {
      setBuildError(e instanceof Error ? e.message : 'Build failed')
    }
  }

  async function handleSwap(slot: string, cardId: string) {
    if (!builtSquad) return
    setDropdownSlot(null)
    const prev = builtSquad
    const newSquad: SquadFile = {
      ...builtSquad,
      starting_xi: { ...builtSquad.starting_xi, [slot]: cardId },
    }
    setBuiltSquad(newSquad)
    try {
      const report = await chemMutation.mutateAsync(newSquad)
      setChemReport(report)
    } catch {
      setBuiltSquad(prev)
    }
  }

  async function handleSave() {
    if (!builtSquad) return
    setSaveError(null)
    setSaveSuccess(false)
    try {
      await saveMutation.mutateAsync({ name: squadName, squad: { ...builtSquad, name: squadName } })
      setSaveSuccess(true)
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : 'Save failed')
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-4">Build</h1>

      <div className="flex flex-wrap gap-3 mb-4 items-end">
        <div className="flex flex-col gap-1">
          <label htmlFor="formation-select" className="text-muted text-xs uppercase tracking-wider">Formation</label>
          <select
            id="formation-select"
            value={formation}
            onChange={e => setFormation(e.target.value)}
            className="bg-card border border-border rounded px-2 py-1.5 text-sm text-white focus:outline-none focus:border-gold"
          >
            {formations.map(f => <option key={f} value={f}>{f}</option>)}
          </select>
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="budget-input" className="text-muted text-xs uppercase tracking-wider">Budget</label>
          <input
            id="budget-input"
            type="text"
            inputMode="numeric"
            placeholder="e.g. 500K or 5M"
            value={budget}
            onChange={e => setBudget(e.target.value)}
            className="bg-card border border-border rounded px-3 py-1.5 text-sm text-white placeholder-muted w-36 focus:outline-none focus:border-gold"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="league-filter" className="text-muted text-xs uppercase tracking-wider">League (optional)</label>
          <select
            id="league-filter"
            value={league}
            onChange={e => setLeague(e.target.value)}
            className="bg-card border border-border rounded px-2 py-1.5 text-sm text-white focus:outline-none focus:border-gold"
          >
            <option value="">Any</option>
            {(meta?.leagues ?? []).map(l => <option key={l} value={l}>{l}</option>)}
          </select>
        </div>

        <button
          onClick={handleBuild}
          disabled={!budget || buildMutation.isPending}
          className="px-4 py-2 bg-gold text-navy font-bold rounded text-sm disabled:opacity-50 self-end"
        >
          {buildMutation.isPending ? 'Building…' : 'Build'}
        </button>
      </div>

      {buildError && (
        <div className="text-red-400 bg-red-900/20 border border-red-800 rounded p-3 mb-4">
          {buildError}
        </div>
      )}

      {builtSquad && (
        <div className="flex gap-4 relative">
          <div className="flex-1 relative">
            <Pitch
              formationSlots={formationSlots}
              slotCards={slotCards}
              chemReport={chemReport}
              selectedSlot={selectedSlot}
              onSlotClick={slot => { setSelectedSlot(slot); setDropdownSlot(slot) }}
            />

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

            <div className="mt-3 flex items-center gap-3 flex-wrap">
              <input
                type="text"
                value={squadName}
                onChange={e => setSquadName(e.target.value)}
                placeholder="Squad name"
                className="bg-card border border-border rounded px-3 py-1.5 text-sm text-white w-36 focus:outline-none focus:border-gold"
              />
              <button
                onClick={handleSave}
                disabled={saveMutation.isPending || !squadName}
                className="px-4 py-2 bg-gold text-navy font-medium rounded text-sm disabled:opacity-50"
              >
                {saveMutation.isPending ? 'Saving…' : 'Save squad'}
              </button>
              {saveSuccess && <span className="text-chem text-sm">Saved</span>}
              {saveError && <span className="text-red-400 text-sm">{saveError}</span>}
            </div>
          </div>

          <SidePanel slot={selectedSlot} card={selectedCard} chemReport={chemReport} />
        </div>
      )}
    </div>
  )
}
