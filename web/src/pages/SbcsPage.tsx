import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../api/client'
import SkeletonGrid from '../components/SkeletonGrid'

interface SbcChallenge {
  name: string
  description: string
  requirements: string[]
  cost: number | null
}

interface Sbc {
  slug: string
  name: string
  category: string
  description: string
  cost: number | null
  cost_complete: boolean
  cost_pc: number | null
  reward_packs: string[]
  reward_player_ea_ids: number[]
  repeatable: boolean
  number_of_repeats: number | null
  challenges?: SbcChallenge[]
  source_url: string
}

const CATEGORY_LABEL: Record<string, string> = {
  upgrades: 'Upgrade',
  challenges: 'Challenge',
  players: 'Player',
  icons: 'Icon',
  swaps: 'Swap',
  foundations: 'Foundation',
}

function formatCost(cost: number | null, complete: boolean) {
  if (cost === null) return 'No solution'
  if (cost === 0) return 'Free'
  return `${cost.toLocaleString()}c${complete ? '' : '+'}`
}

function reward(sbc: Sbc) {
  if (sbc.reward_packs.length > 0) return sbc.reward_packs.join(', ')
  if (sbc.reward_player_ea_ids.length > 0) return `Player: ${sbc.name}`
  return 'Player pick / special'
}

export default function SbcsPage() {
  const { data, isPending, error } = useQuery({
    queryKey: ['sbcs'],
    queryFn: () => apiFetch<{ sbcs: Sbc[] }>('/api/sbcs'),
  })
  const sbcs = data?.sbcs ?? []

  return (
    <div>
      <h1 className="text-2xl font-bold text-fg mb-1">SBCs</h1>
      <p className="text-muted text-sm mb-4">
        Best Squad Building Challenges to do right now — scraped live from the fut.gg SBC hub.
        Ranked so cheap, repeatable pack &amp; upgrade SBCs surface first. Cost is fut.gg’s
        cheapest console solution. Each SBC lists what every squad needs to complete it.
      </p>

      {error && (
        <div className="text-red-400 bg-red-900/20 border border-red-800 rounded p-3 mb-4">
          {error.message}
        </div>
      )}

      {data && <p className="text-muted text-sm mb-3">{sbcs.length} active SBCs</p>}

      {isPending ? (
        <SkeletonGrid />
      ) : sbcs.length === 0 ? (
        <p className="text-muted text-sm">No SBCs available right now.</p>
      ) : (
        <div className="flex flex-col gap-2">
          {sbcs.map(sbc => (
            <div
              key={sbc.slug}
              className="bg-card border border-border rounded p-3"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-fg font-semibold">{sbc.name}</span>
                    <span className="text-xs bg-navy text-muted rounded px-1.5 py-0.5">
                      {CATEGORY_LABEL[sbc.category] ?? sbc.category}
                    </span>
                    {sbc.repeatable && (
                      <span className="text-xs bg-gold/20 text-gold rounded px-1.5 py-0.5">
                        Repeatable
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-muted mt-1">{reward(sbc)}</p>
                  {sbc.description && (
                    <p className="text-xs text-muted/70 mt-1 line-clamp-2">{sbc.description}</p>
                  )}
                </div>
                <div className="text-right shrink-0">
                  <div className="text-gold font-bold">
                    {formatCost(sbc.cost, sbc.cost_complete)}
                  </div>
                  <div className="text-[10px] text-muted">cheapest</div>
                </div>
              </div>
              {(sbc.challenges ?? []).length > 0 ? (
                <ol className="mt-3 space-y-2 border-t border-border pt-2">
                  {(sbc.challenges ?? []).map((ch, i) => (
                    <li key={i}>
                      <div className="flex items-baseline justify-between gap-3">
                        <span className="text-sm text-fg">
                          {(sbc.challenges ?? []).length > 1 && (
                            <span className="text-muted mr-1.5">{i + 1}.</span>
                          )}
                          {ch.name}
                        </span>
                        <span className="text-xs text-gold shrink-0">
                          {formatCost(ch.cost, true)}
                        </span>
                      </div>
                      {ch.requirements.length > 0 ? (
                        <ul className="mt-1 space-y-0.5">
                          {ch.requirements.map((req, j) => (
                            <li key={j} className="text-xs text-muted leading-snug flex gap-1.5">
                              <span className="text-gold shrink-0">•</span>
                              <span>{req}</span>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="mt-1 text-xs text-muted/60 italic">No requirements listed.</p>
                      )}
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="mt-2 text-xs text-muted/60 italic">
                  Requirements not scraped yet — run fc26 refresh-sbcs.
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
