import { useState, useEffect, useRef } from 'react'
import { useMeta } from '../api/meta'
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
        className="bg-card border border-border rounded px-3 py-1.5 text-sm text-white placeholder-muted focus:outline-none focus:border-gold"
      />

      <div className="flex items-center gap-1">
        <label htmlFor="pos-select" className="text-muted text-sm sr-only">Position</label>
        <select
          id="pos-select"
          aria-label="Position"
          value={params.pos ?? ''}
          onChange={e => onChange({ ...params, pos: e.target.value || undefined, offset: 0 })}
          className="bg-card border border-border rounded px-2 py-1.5 text-sm text-white focus:outline-none focus:border-gold"
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
        className="bg-card border border-border rounded px-2 py-1.5 text-sm text-white focus:outline-none focus:border-gold"
      >
        <option value="">All leagues</option>
        {(meta?.leagues ?? []).map(l => <option key={l} value={l}>{l}</option>)}
      </select>

      <select
        aria-label="Version"
        value={params.version ?? ''}
        onChange={e => onChange({ ...params, version: e.target.value || undefined, offset: 0 })}
        className="bg-card border border-border rounded px-2 py-1.5 text-sm text-white focus:outline-none focus:border-gold"
      >
        <option value="">All versions</option>
        {(meta?.versions ?? []).map(v => <option key={v} value={v}>{v}</option>)}
      </select>

      <input
        type="number"
        placeholder="Min OVR"
        min={1}
        max={99}
        value={params.min_ovr ?? ''}
        onChange={e => onChange({ ...params, min_ovr: e.target.value ? Number(e.target.value) : undefined, offset: 0 })}
        className="bg-card border border-border rounded px-3 py-1.5 text-sm text-white placeholder-muted w-24 focus:outline-none focus:border-gold"
      />

      <select
        aria-label="Sort"
        value={params.sort ?? 'ovr'}
        onChange={e => onChange({ ...params, sort: e.target.value, offset: 0 })}
        className="bg-card border border-border rounded px-2 py-1.5 text-sm text-white focus:outline-none focus:border-gold"
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
