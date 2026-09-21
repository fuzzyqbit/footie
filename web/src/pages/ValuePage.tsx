import { useState } from 'react'
import { useValue } from '../api/value'
import { useSquads } from '../api/squads'
import { useMeta } from '../api/meta'
import CardTile from '../components/CardTile'
import SearchSelect from '../components/SearchSelect'
import SkeletonGrid from '../components/SkeletonGrid'

// Face stats; GK cards keep the keeper attributes in the same slots.
const STATS = [
  { key: 'pac', out: 'PAC', gk: 'DIV' }, { key: 'sho', out: 'SHO', gk: 'HAN' },
  { key: 'pas', out: 'PAS', gk: 'KIC' }, { key: 'dri', out: 'DRI', gk: 'REF' },
  { key: 'def', out: 'DEF', gk: 'SPD' }, { key: 'phy', out: 'PHY', gk: 'POS' },
]

const POSITIONS = ['GK', 'CB', 'RB', 'LB', 'CDM', 'CM', 'CAM', 'RM', 'LM', 'RW', 'LW', 'ST', 'CF']

export default function ValuePage() {
  const [pos, setPos] = useState('')
  const [maxPrice, setMaxPrice] = useState<number | undefined>(50000)
  const [squad, setSquad] = useState('')
  const [league, setLeague] = useState('')
  const [nation, setNation] = useState('')
  const [club, setClub] = useState('')
  const [minPrice, setMinPrice] = useState<number | undefined>(undefined)
  const [stat, setStat] = useState('')
  const [statMin, setStatMin] = useState<number | undefined>(undefined)

  const { data: squads } = useSquads()
  const { data: meta } = useMeta()
  const { data, isPending, error } = useValue({
    per_tier: 6,
    limit: 120,
    pos: pos || undefined,
    max_price: maxPrice,
    min_price: minPrice,
    stat: stat || undefined,
    stat_min: statMin,
    squad: squad || undefined,
    league: league || undefined,
    nation: nation || undefined,
    club: club || undefined,
  })
  const picks = data?.picks ?? []

  const inputCls =
    'bg-card border border-border rounded px-2 py-1.5 text-sm text-fg focus:outline-none focus:border-gold'

  return (
    <div>
      <h1 className="text-2xl font-bold text-fg mb-1">Value</h1>
      <p className="text-muted text-sm mb-4">
        Best bargains at each rating tier — cheap, underrated cards by rating-per-coin.
      </p>

      <div className="flex flex-wrap gap-3 mb-4">
        <select aria-label="Position" value={pos} onChange={e => setPos(e.target.value)} className={inputCls}>
          <option value="">All positions</option>
          {POSITIONS.map(p => <option key={p} value={p}>{p}</option>)}
        </select>

        <select aria-label="Squad" value={squad} onChange={e => setSquad(e.target.value)} className={inputCls}>
          <option value="">Any squad</option>
          {(squads ?? []).map(s => <option key={s.name} value={s.name}>For: {s.name}</option>)}
        </select>

        <select aria-label="League" value={league} onChange={e => setLeague(e.target.value)} className={inputCls}>
          <option value="">All leagues</option>
          {(meta?.leagues ?? []).map(l => <option key={l} value={l}>{l}</option>)}
        </select>

        <SearchSelect label="Nation" placeholder="Any nation" value={nation}
          options={meta?.nations ?? []} onChange={setNation} />

        <SearchSelect label="Club" placeholder="Any club" value={club}
          options={meta?.clubs ?? []} onChange={setClub} className="w-40" />

        <select aria-label="Stat filter" value={stat} onChange={e => setStat(e.target.value)} className={inputCls}>
          <option value="">Stat ≥</option>
          {STATS.map(s => (
            <option key={s.key} value={s.key}>{pos === 'GK' ? s.gk : s.out}</option>
          ))}
        </select>

        <input
          type="number"
          aria-label="Min stat"
          placeholder="Min"
          min={1}
          max={99}
          disabled={!stat}
          value={statMin ?? ''}
          onChange={e => setStatMin(e.target.value ? Number(e.target.value) : undefined)}
          className={`${inputCls} w-20 placeholder-muted disabled:opacity-40`}
        />

        <input
          type="number"
          aria-label="Min price"
          placeholder="Min price"
          min={0}
          step={1000}
          value={minPrice ?? ''}
          onChange={e => setMinPrice(e.target.value ? Number(e.target.value) : undefined)}
          className={`${inputCls} w-32 placeholder-muted`}
        />

        <input
          type="number"
          aria-label="Max price"
          placeholder="Max price"
          min={1}
          value={maxPrice ?? ''}
          onChange={e => setMaxPrice(e.target.value ? Number(e.target.value) : undefined)}
          className={`${inputCls} w-32 placeholder-muted`}
        />
      </div>

      {error && (
        <div className="text-red-400 bg-red-900/20 border border-red-800 rounded p-3 mb-4">
          {error.message}
        </div>
      )}

      {isPending ? (
        <SkeletonGrid />
      ) : picks.length === 0 ? (
        <p className="text-muted text-sm">No value picks match the filters.</p>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
          {picks.map(pick => (
            <div key={pick.id}>
              <CardTile card={pick} />
              <div className="flex justify-between text-xs text-muted mt-1 px-1">
                <span>{pick.best_pos}</span>
                <span title="rating per 1000 coins">{pick.value.toFixed(1)} / 1k</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
