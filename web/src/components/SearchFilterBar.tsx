import { useState, useEffect, useRef } from 'react'
import { useMeta } from '../api/meta'
import SearchSelect from './SearchSelect'
import type { CardParams } from '../api/cards'

interface Props {
  params: CardParams
  onChange: (params: CardParams) => void
}

// Sort options over the six face stats. GK cards store the keeper attribute set
// in the same slots, so relabel them when GK is the selected position.
const STAT_SORTS: Array<{ key: string; out: string; gk: string }> = [
  { key: 'pac', out: 'PAC', gk: 'DIV' },
  { key: 'sho', out: 'SHO', gk: 'HAN' },
  { key: 'pas', out: 'PAS', gk: 'KIC' },
  { key: 'dri', out: 'DRI', gk: 'REF' },
  { key: 'def', out: 'DEF', gk: 'SPD' },
  { key: 'phy', out: 'PHY', gk: 'POS' },
]

export default function SearchFilterBar({ params, onChange }: Props) {
  const { data: meta } = useMeta()
  const [searchInput, setSearchInput] = useState(params.search ?? '')
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      onChange({ ...params, search: searchInput || undefined, offset: 0 })
    }, 300)
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [searchInput])

  return (
    <div className="flex flex-wrap gap-3 mb-4">
      <input
        type="text"
        placeholder="Search players..."
        value={searchInput}
        onChange={e => setSearchInput(e.target.value)}
        className="bg-card border border-border rounded px-3 py-1.5 text-sm text-fg placeholder-muted focus:outline-none focus:border-gold"
      />

      <div className="flex items-center gap-1">
        <label htmlFor="pos-select" className="text-muted text-sm sr-only">Position</label>
        <select
          id="pos-select"
          aria-label="Position"
          value={params.pos ?? ''}
          onChange={e => onChange({ ...params, pos: e.target.value || undefined, offset: 0 })}
          className="bg-card border border-border rounded px-2 py-1.5 text-sm text-fg focus:outline-none focus:border-gold"
        >
          <option value="">All positions</option>
          {['GK', 'CB', 'RB', 'LB', 'CDM', 'CM', 'CAM', 'RM', 'LM', 'RW', 'LW', 'ST', 'CF', 'SS'].map(p => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
      </div>

      <select
        aria-label="League"
        value={params.league ?? ''}
        onChange={e => onChange({ ...params, league: e.target.value || undefined, offset: 0 })}
        className="bg-card border border-border rounded px-2 py-1.5 text-sm text-fg focus:outline-none focus:border-gold"
      >
        <option value="">All leagues</option>
        {(meta?.leagues ?? []).map(l => <option key={l} value={l}>{l}</option>)}
      </select>

      <SearchSelect
        label="Nation"
        placeholder="Any nation"
        value={params.nation ?? ''}
        options={meta?.nations ?? []}
        onChange={v => onChange({ ...params, nation: v || undefined, offset: 0 })}
      />

      <SearchSelect
        label="Club"
        placeholder="Any club"
        value={params.club ?? ''}
        options={meta?.clubs ?? []}
        onChange={v => onChange({ ...params, club: v || undefined, offset: 0 })}
        className="w-40"
      />

      <SearchSelect
        label="Version"
        placeholder="Any version (Icon, Hero…)"
        value={params.version ?? ''}
        options={meta?.versions ?? []}
        onChange={v => onChange({ ...params, version: v || undefined, offset: 0 })}
      />

      <input
        type="number"
        placeholder="Min OVR"
        min={1}
        max={99}
        value={params.min_ovr ?? ''}
        onChange={e => onChange({ ...params, min_ovr: e.target.value ? Number(e.target.value) : undefined, offset: 0 })}
        className="bg-card border border-border rounded px-3 py-1.5 text-sm text-fg placeholder-muted w-24 focus:outline-none focus:border-gold"
      />

      <select
        aria-label="Stat filter"
        value={params.stat ?? ''}
        onChange={e => onChange({ ...params, stat: e.target.value || undefined, offset: 0 })}
        className="bg-card border border-border rounded px-2 py-1.5 text-sm text-fg focus:outline-none focus:border-gold"
      >
        <option value="">Stat ≥</option>
        {STAT_SORTS.map(({ key, out, gk }) => (
          <option key={key} value={key}>{params.pos === 'GK' ? gk : out}</option>
        ))}
      </select>

      <input
        type="number"
        aria-label="Min stat"
        placeholder="Min"
        min={1}
        max={99}
        disabled={!params.stat}
        value={params.stat_min ?? ''}
        onChange={e => onChange({ ...params, stat_min: e.target.value ? Number(e.target.value) : undefined, offset: 0 })}
        className="bg-card border border-border rounded px-3 py-1.5 text-sm text-fg placeholder-muted w-20 focus:outline-none focus:border-gold disabled:opacity-40"
      />

      <select
        aria-label="Sort"
        value={params.sort ?? 'ovr'}
        onChange={e => onChange({ ...params, sort: e.target.value, offset: 0 })}
        className="bg-card border border-border rounded px-2 py-1.5 text-sm text-fg focus:outline-none focus:border-gold"
      >
        <option value="ovr">OVR ↓</option>
        {STAT_SORTS.map(({ key, out, gk }) => (
          <option key={key} value={key}>
            {(params.pos === 'GK' ? gk : out)} ↓
          </option>
        ))}
        <option value="name">Name A–Z</option>
      </select>
    </div>
  )
}
