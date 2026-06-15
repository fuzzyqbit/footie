import { useState } from 'react'
import type { Card, FaceStats } from '../types'
import { useWatchlist } from '../watchlist'
import { displayName } from '../displayName'
import CompareRadar from '../components/CompareRadar'

const COLORS = ['#e2b714', '#4caf50', '#3b82f6']
const MAX = COLORS.length

const STAT_ROWS: Array<[string, keyof FaceStats]> = [
  ['PAC', 'pac'],
  ['SHO', 'sho'],
  ['PAS', 'pas'],
  ['DRI', 'dri'],
  ['DEF', 'def_'],
  ['PHY', 'phy'],
]

function formatPrice(price: number | null): string {
  if (price == null) return '—'
  if (price >= 1_000_000) return `${(price / 1_000_000).toFixed(1)}M`
  if (price >= 1_000) return `${(price / 1_000).toFixed(0)}K`
  return String(price)
}

// best value in a row; higherBetter=false picks the min (e.g. price)
function bestIndex(vals: Array<number | null>, higherBetter: boolean): number {
  let best = -1
  let bestVal: number | null = null
  vals.forEach((v, i) => {
    if (v == null) return
    if (bestVal == null || (higherBetter ? v > bestVal : v < bestVal)) {
      bestVal = v
      best = i
    }
  })
  return best
}

export default function ComparePage() {
  const flagged = useWatchlist()
  const [selected, setSelected] = useState<string[]>([])

  const chosen = selected
    .map(id => flagged.find(c => c.id === id))
    .filter((c): c is Card => c != null)

  function toggle(id: string) {
    setSelected(s =>
      s.includes(id) ? s.filter(x => x !== id) : s.length < MAX ? [...s, id] : s,
    )
  }

  const colorOf = (id: string) => {
    const i = selected.indexOf(id)
    return i === -1 ? undefined : COLORS[i]
  }

  const numberRow = (
    label: string,
    vals: Array<number | null>,
    higherBetter: boolean,
    fmt: (v: number) => string = v => String(v),
  ) => {
    const best = bestIndex(vals, higherBetter)
    return (
      <tr key={label} className="border-t border-border">
        <td className="text-muted py-1 pr-3">{label}</td>
        {vals.map((v, i) => (
          <td
            key={i}
            className={`py-1 px-3 text-right ${i === best ? 'text-gold font-semibold' : 'text-white'}`}
          >
            {v == null ? '—' : fmt(v)}
          </td>
        ))}
      </tr>
    )
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-1">Compare</h1>
      <p className="text-muted text-sm mb-4">
        Pick up to {MAX} flagged players to overlay their stats. Best value in each row is gold.
      </p>

      {flagged.length === 0 ? (
        <p className="text-muted text-sm">
          No flagged players yet. Flag players with the star on any card, then come back to compare them.
        </p>
      ) : (
        <>
          <div className="flex flex-wrap gap-2 mb-5">
            {flagged.map(card => {
              const color = colorOf(card.id)
              const disabled = !color && selected.length >= MAX
              return (
                <button
                  key={card.id}
                  type="button"
                  onClick={() => toggle(card.id)}
                  disabled={disabled}
                  className={`flex items-center gap-2 rounded px-2.5 py-1.5 text-sm border transition-colors ${
                    color
                      ? 'bg-navy text-white'
                      : disabled
                        ? 'bg-card text-muted border-border opacity-40 cursor-not-allowed'
                        : 'bg-card text-white border-border hover:bg-card-hover'
                  }`}
                  style={color ? { borderColor: color } : undefined}
                >
                  {color && (
                    <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: color }} />
                  )}
                  <span className="text-gold font-bold">{card.ovr}</span>
                  <span className="truncate max-w-32" title={card.player_name}>
                    {displayName(card.player_name)}
                  </span>
                </button>
              )
            })}
          </div>

          {chosen.length === 0 ? (
            <p className="text-muted text-sm">Select one or more players above to compare.</p>
          ) : (
            <div className="flex flex-col lg:flex-row gap-6 items-start">
              <CompareRadar
                series={chosen.map((c, i) => ({
                  label: c.id,
                  color: COLORS[i],
                  values: STAT_ROWS.map(([, key]) => c.face[key]),
                }))}
              />

              <table className="text-sm border-collapse">
                <thead>
                  <tr>
                    <th className="text-left text-muted font-medium py-1 pr-3">Stat</th>
                    {chosen.map((c, i) => (
                      <th key={c.id} className="py-1 px-3 text-right">
                        <span className="inline-flex items-center gap-1.5 justify-end">
                          <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: COLORS[i] }} />
                          <span className="text-white truncate max-w-28" title={c.player_name}>
                            {displayName(c.player_name)}
                          </span>
                        </span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {numberRow('OVR', chosen.map(c => c.ovr), true)}
                  {STAT_ROWS.map(([label, key]) =>
                    numberRow(label, chosen.map(c => c.face[key]), true),
                  )}
                  {numberRow('Price', chosen.map(c => c.price), false, formatPrice)}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  )
}
