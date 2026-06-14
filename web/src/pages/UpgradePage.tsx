import { useState } from 'react'
import { useSquads, useSquad, useSaveSquad } from '../api/squads'
import { useUpgrade } from '../api/upgrade'
import type { SquadFile, UpgradePlan, Swap } from '../types'

function formatCoins(n: number): string {
  if (Math.abs(n) >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (Math.abs(n) >= 1_000) return `${(n / 1_000).toFixed(0)}K`
  return String(n)
}

export default function UpgradePage() {
  const { data: squadList } = useSquads()
  const [selectedName, setSelectedName] = useState('')
  const [budget, setBudget] = useState('')
  const [plan, setPlan] = useState<UpgradePlan | null>(null)
  const [upgradeError, setUpgradeError] = useState<string | null>(null)
  const [saveSuccess, setSaveSuccess] = useState(false)

  const { data: loadedSquad } = useSquad(selectedName || null)
  const upgradeMutation = useUpgrade()
  const saveMutation = useSaveSquad()

  async function handleFindUpgrades() {
    if (!loadedSquad || !budget) return
    setUpgradeError(null)
    setPlan(null)
    setSaveSuccess(false)
    try {
      const result = await upgradeMutation.mutateAsync({ squad: loadedSquad, budget })
      setPlan(result)
    } catch (e) {
      setUpgradeError(e instanceof Error ? e.message : 'Upgrade failed')
    }
  }

  function buildModifiedSquad(swapsToApply: Swap[]): SquadFile | null {
    if (!loadedSquad) return null
    const xi = { ...loadedSquad.starting_xi }
    for (const swap of swapsToApply) xi[swap.slot] = swap.in_id
    return { ...loadedSquad, starting_xi: xi }
  }

  async function handleSaveModified() {
    if (!plan || !loadedSquad || !selectedName) return
    const modified = buildModifiedSquad(plan.swaps)
    if (!modified) return
    setSaveSuccess(false)
    try {
      await saveMutation.mutateAsync({ name: `${selectedName}-upgraded`, squad: modified })
      setSaveSuccess(true)
    } catch {}
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-4">Upgrade</h1>

      <div className="flex flex-wrap gap-3 mb-4 items-end">
        <div className="flex flex-col gap-1">
          <label htmlFor="squad-select" className="text-muted text-xs uppercase tracking-wider">Squad</label>
          <select
            id="squad-select"
            value={selectedName}
            onChange={e => setSelectedName(e.target.value)}
            className="bg-card border border-border rounded px-2 py-1.5 text-sm text-white focus:outline-none focus:border-gold"
          >
            <option value="">Select squad…</option>
            {(squadList ?? []).map(s => (
              <option key={s.name} value={s.name}>{s.name}</option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="upgrade-budget" className="text-muted text-xs uppercase tracking-wider">Budget</label>
          <input
            id="upgrade-budget"
            type="text"
            placeholder="e.g. 500K"
            value={budget}
            onChange={e => setBudget(e.target.value)}
            className="bg-card border border-border rounded px-3 py-1.5 text-sm text-white placeholder-muted w-28 focus:outline-none focus:border-gold"
          />
        </div>

        <button
          onClick={handleFindUpgrades}
          disabled={!selectedName || !budget || upgradeMutation.isPending}
          className="px-4 py-2 bg-gold text-navy font-bold rounded text-sm disabled:opacity-50 self-end"
        >
          {upgradeMutation.isPending ? 'Searching…' : 'Find upgrades'}
        </button>
      </div>

      {upgradeError && (
        <div className="text-red-400 bg-red-900/20 border border-red-800 rounded p-3 mb-4">
          {upgradeError}
        </div>
      )}

      {plan && plan.swaps.length === 0 && (
        <div className="text-muted text-sm">No upgrades found within budget.</div>
      )}

      {plan && plan.swaps.length > 0 && (
        <div>
          <div className="text-muted text-sm mb-3">
            {plan.swaps.length} swap{plan.swaps.length !== 1 ? 's' : ''} found ·
            Chem {plan.chem_before}→{plan.chem_after}/33
          </div>

          <div className="space-y-2 mb-4">
            {plan.swaps.map(swap => (
              <div
                key={`${swap.slot}-${swap.in_id}`}
                className="bg-card border border-border rounded-lg p-3 flex items-center gap-4"
              >
                <span className="text-muted text-xs w-10">{swap.slot}</span>
                <div className="flex-1">
                  <span className="text-muted line-through text-sm">{swap.out_name}</span>
                  <span className="text-muted mx-2">→</span>
                  <span className="text-white font-medium text-sm">{swap.in_name}</span>
                  <span className="text-muted text-xs ml-1">{swap.in_version}</span>
                </div>
                <div className="text-right">
                  <div className={`text-sm font-medium ${swap.net_cost <= 0 ? 'text-chem' : 'text-red-400'}`}>
                    {swap.net_cost <= 0 ? '-' : '+'}{formatCoins(Math.abs(swap.net_cost))}
                  </div>
                  {swap.chem_delta !== 0 && (
                    <div className={`text-xs ${swap.chem_delta > 0 ? 'text-chem' : 'text-red-400'}`}>
                      chem {swap.chem_delta > 0 ? '+' : ''}{swap.chem_delta}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={handleSaveModified}
              disabled={saveMutation.isPending}
              className="px-4 py-2 bg-gold text-navy font-medium rounded text-sm disabled:opacity-50"
            >
              {saveMutation.isPending ? 'Saving…' : 'Save upgraded squad'}
            </button>
            {saveSuccess && <span className="text-chem text-sm">Saved as {selectedName}-upgraded</span>}
          </div>
        </div>
      )}
    </div>
  )
}
