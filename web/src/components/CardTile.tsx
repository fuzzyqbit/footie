import { useState } from 'react'
import type { ReactNode } from 'react'
import type { Card } from '../types'
import { faceKeys } from '../faceLabels'
import { useIsWatched, toggleWatch } from '../watchlist'
import { statColor, tierColor } from '../statColor'
import { displayName } from '../displayName'
import StatRadar from './StatRadar'

interface Props {
  card: Card
}

function formatPrice(price: number | null): string {
  if (price == null) return '—'
  if (price >= 1_000_000) return `${(price / 1_000_000).toFixed(1)}M`
  if (price >= 1_000) return `${(price / 1_000).toFixed(0)}K`
  return String(price)
}

const NAME_PARTICLES = new Set([
  'de', 'del', 'van', 'von', 'der', 'den', 'dos', 'das', 'da', 'di',
  'le', 'la', 'el', 'bin', 'al', 'ben', 'mc', 'mac',
])

// Card-art prints the short name players know: futbin's scraped common name when
// we have it (e.g. "Balde" for "Alejandro Balde Martínez"), else a known-icon
// alias, else the surname (keeping a trailing particle like "De Bruyne"). Long
// Spanish/Brazilian full names overflow the frame otherwise.
function cardArtName(card: Card): string {
  if (card.common_name) return card.common_name
  const name = card.player_name
  const aliased = displayName(name)
  if (aliased !== name) return aliased
  const parts = name.trim().split(/\s+/)
  if (parts.length <= 1) return name
  const last = parts[parts.length - 1]
  const prev = parts[parts.length - 2]
  return NAME_PARTICLES.has(prev.toLowerCase()) ? `${prev} ${last}` : last
}

// PlayStyle+ chips: the card's standout abilities. Subtle gold pill that stays
// legible on a white tile (light) and a dark tile (dark). Renders nothing when
// the card has no PlayStyle+ entries.
function PlayStylesPlus({ styles, className = '' }: { styles: string[]; className?: string }) {
  if (!styles.length) return null
  return (
    <div className={'flex flex-wrap gap-1 ' + className}>
      {styles.map(name => (
        <span
          key={name}
          className="rounded px-1.5 py-0.5 text-[0.65rem] leading-none font-semibold bg-gold/20 text-gold ring-1 ring-gold/30"
        >
          {name}
        </span>
      ))}
    </div>
  )
}

// One labelled fact row in the expanded detail (e.g. "Height  190 cm").
function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-baseline gap-2 text-xs">
      <span className="text-muted w-28 shrink-0">{label}</span>
      <span className="text-fg flex-1">{children}</span>
    </div>
  )
}

// Expanded stat detail (radar + per-stat bars), GK-aware via faceKeys.
function StatDetail({ card }: Props) {
  const stats = faceKeys(card.position).map(
    ([key, label]) => [label, card.face[key]] as const,
  )
  return (
    <div className="mt-2 pt-2 border-t border-border flex flex-col gap-1">
      <div className="flex items-center gap-3">
      <StatRadar values={stats.map(([, v]) => v)} />
      <div className="flex-1 flex flex-col gap-1">
        {stats.map(([label, v]) => (
          <div key={label} className="flex items-center gap-1.5 text-xs">
            <span className="text-muted w-7 shrink-0">{label}</span>
            <div className="flex-1 h-1.5 rounded bg-border overflow-hidden">
              <div
                className="h-full rounded"
                style={{ width: `${v ?? 0}%`, backgroundColor: statColor(v) }}
              />
            </div>
            <span className="text-fg w-6 text-right">{v ?? '—'}</span>
          </div>
        ))}
      </div>
      </div>
      <div className="mt-2 flex flex-col gap-1">
        <Fact label="Preferred position">{card.position}</Fact>
        <Fact label="Alternate positions">
          {card.alt_positions.length ? card.alt_positions.join(', ') : '—'}
        </Fact>
        <Fact label="Height">{card.height_cm != null ? `${card.height_cm} cm` : '—'}</Fact>
        {card.playstyles_plus.length > 0 && (
          <div className="flex items-baseline gap-2 text-xs">
            <span className="text-muted w-28 shrink-0">PlayStyles+</span>
            <PlayStylesPlus styles={card.playstyles_plus} className="flex-1" />
          </div>
        )}
        {card.playstyles.length > 0 && (
          <Fact label="PlayStyles">{card.playstyles.join(', ')}</Fact>
        )}
      </div>
    </div>
  )
}

// Real FUT card: futbin's signed card-frame PNG + cut-out player render, with
// rating/position/name/stats overlaid the way the in-game card lays them out.
// GK-aware: face stat labels follow the card's position (faceKeys).
function CardArt({ card }: Props) {
  const stats = faceKeys(card.position)
  return (
    <div className="relative w-full aspect-[7/10] select-none rounded-md bg-[#0f0f1a]">
      <img
        src={card.bg_url!}
        alt=""
        aria-hidden
        className="absolute inset-0 w-full h-full object-contain"
      />
      <img
        src={card.image_url!}
        alt={card.player_name}
        loading="lazy"
        className="absolute left-1/2 top-[14%] w-[62%] -translate-x-1/2 object-contain drop-shadow"
      />
      <div
        className="absolute left-[15%] top-[17%] flex flex-col items-center leading-none"
        style={{ textShadow: '0 0 2px rgba(0,0,0,0.95), 0 1px 3px rgba(0,0,0,0.85)' }}
      >
        <span className="text-white font-extrabold text-[clamp(0.9rem,4vw,1.6rem)]">{card.ovr}</span>
        <span className="text-white font-bold text-[clamp(0.5rem,2.2vw,0.8rem)]">{card.position}</span>
      </div>
      <div
        className="absolute inset-x-0 top-[60%] text-center px-2"
        style={{ textShadow: '0 0 2px rgba(0,0,0,0.95), 0 1px 3px rgba(0,0,0,0.85)' }}
      >
        <div className="text-white font-bold uppercase tracking-tight truncate text-[clamp(0.55rem,3vw,1rem)]">
          {cardArtName(card)}
        </div>
      </div>
      <div
        className="absolute inset-x-[12%] bottom-[14%] grid grid-cols-3 gap-x-2 gap-y-0.5 text-white"
        style={{ textShadow: '0 0 2px rgba(0,0,0,0.95), 0 1px 3px rgba(0,0,0,0.85)' }}
      >
        {stats.map(([key, label]) => (
          <div key={key} className="flex justify-center gap-1 text-[clamp(0.45rem,2.2vw,0.75rem)] font-semibold">
            <span>{card.face[key] ?? '—'}</span>
            <span className="opacity-70">{label}</span>
          </div>
        ))}
      </div>
      {(card.club_url || card.league_url || card.nation_url) && (
        <div className="absolute inset-x-0 bottom-[3%] flex items-center justify-center gap-2">
          {card.club_url && (
            <img src={card.club_url} alt="" aria-hidden loading="lazy" className="h-4 w-auto object-contain drop-shadow" />
          )}
          {card.league_url && (
            <img src={card.league_url} alt="" aria-hidden loading="lazy" className="h-4 w-auto object-contain drop-shadow" />
          )}
          {card.nation_url && (
            <img src={card.nation_url} alt="" aria-hidden loading="lazy" className="h-4 w-auto object-contain drop-shadow" />
          )}
        </div>
      )}
    </div>
  )
}

export default function CardTile({ card }: Props) {
  const [expanded, setExpanded] = useState(false)
  const watched = useIsWatched(card.id)
  const hasArt = Boolean(card.bg_url && card.image_url)

  if (hasArt) {
    return (
      <div
        className="bg-card rounded-lg p-1 cursor-pointer hover:bg-card-hover transition-colors border border-border"
        style={{ borderLeftColor: tierColor(card.ovr, card.version), borderLeftWidth: 3 }}
        onClick={() => setExpanded(e => !e)}
      >
        <CardArt card={card} />
        {card.playstyles_plus.length > 0 && (
          <PlayStylesPlus styles={card.playstyles_plus} className="px-2 pt-1" />
        )}
        <div className="flex items-center justify-between px-2 pb-1 gap-2">
          <span className="text-fg text-xs truncate" title={card.player_name}>
            {displayName(card.player_name)}
          </span>
          <div className="flex items-center gap-1.5 shrink-0">
            <span className="text-chem text-sm font-medium">{formatPrice(card.price)}</span>
            <button
              type="button"
              aria-label={watched ? 'Remove from watchlist' : 'Add to watchlist'}
              aria-pressed={watched}
              onClick={e => {
                e.stopPropagation()
                toggleWatch(card)
              }}
              className={`shrink-0 text-lg leading-none transition-colors ${
                watched ? 'text-gold' : 'text-muted hover:text-fg'
              }`}
            >
              {watched ? '★' : '☆'}
            </button>
          </div>
        </div>
        {expanded && <StatDetail card={card} />}
      </div>
    )
  }

  return (
    <div
      className="bg-card rounded-lg p-3 cursor-pointer hover:bg-card-hover transition-colors border border-border"
      style={{ borderLeftColor: tierColor(card.ovr, card.version), borderLeftWidth: 3 }}
      onClick={() => setExpanded(e => !e)}
    >
      <div className="flex items-center gap-2 mb-1">
        <span className="text-gold font-bold text-lg w-8 text-center">{card.ovr}</span>
        <div className="flex-1 min-w-0">
          <div className="text-fg font-medium truncate" title={card.player_name}>
            {displayName(card.player_name)}
          </div>
          <div className="flex items-center gap-1.5 text-xs min-w-0">
            <span className="text-muted shrink-0">{card.position}</span>
            <span
              className={
                'truncate rounded px-1.5 py-0.5 leading-none ' +
                (card.version.toLowerCase() === 'base'
                  ? 'bg-border text-muted'
                  : 'bg-gold/20 text-gold')
              }
              title={card.version}
            >
              {card.version}
            </span>
          </div>
        </div>
        <div className="text-chem text-sm font-medium">{formatPrice(card.price)}</div>
        <button
          type="button"
          aria-label={watched ? 'Remove from watchlist' : 'Add to watchlist'}
          aria-pressed={watched}
          onClick={e => {
            e.stopPropagation()
            toggleWatch(card)
          }}
          className={`shrink-0 text-lg leading-none transition-colors ${
            watched ? 'text-gold' : 'text-muted hover:text-fg'
          }`}
        >
          {watched ? '★' : '☆'}
        </button>
      </div>

      {card.playstyles_plus.length > 0 && (
        <PlayStylesPlus styles={card.playstyles_plus} className="mt-1.5" />
      )}

      {expanded && <StatDetail card={card} />}
    </div>
  )
}
