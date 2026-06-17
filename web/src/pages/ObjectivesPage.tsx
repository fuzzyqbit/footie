import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../api/client'
import type { Card } from '../types'
import CardTile from '../components/CardTile'
import SkeletonGrid from '../components/SkeletonGrid'

interface ObjectiveCard extends Card {
  objective: string
  objective_url: string
  tasks: string[]
}

export default function ObjectivesPage() {
  const { data, isPending, error } = useQuery({
    queryKey: ['objectives'],
    queryFn: () => apiFetch<{ cards: ObjectiveCard[] }>('/api/objectives'),
  })
  const cards = data?.cards ?? []

  return (
    <div>
      <h1 className="text-2xl font-bold text-fg mb-1">Objectives</h1>
      <p className="text-muted text-sm mb-4">
        Players you unlock by completing objectives — matched from the live fut.gg objectives hub.
        Open a card’s objective for the full task list.
      </p>

      {error && (
        <div className="text-red-400 bg-red-900/20 border border-red-800 rounded p-3 mb-4">
          {error.message}
        </div>
      )}

      {data && <p className="text-muted text-sm mb-3">{cards.length} objective players</p>}

      {isPending ? (
        <SkeletonGrid />
      ) : cards.length === 0 ? (
        <p className="text-muted text-sm">No objective players matched right now.</p>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
          {cards.map(card => (
            <div key={card.id}>
              <CardTile card={card} />
              <a
                href={card.objective_url}
                target="_blank"
                rel="noreferrer"
                className="flex justify-between items-center text-xs mt-1 px-1 text-gold hover:underline"
                title={`Objective: ${card.objective}`}
              >
                <span className="truncate">{card.objective}</span>
                <span className="shrink-0 ml-2">open →</span>
              </a>
              {card.tasks.length > 0 ? (
                <ul className="mt-1 px-1 space-y-1">
                  {card.tasks.map((task, i) => (
                    <li
                      key={i}
                      className="text-xs text-muted leading-snug flex gap-1.5"
                    >
                      <span className="text-gold shrink-0">•</span>
                      <span>{task}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-1 px-1 text-xs text-muted/60 italic">
                  Tasks not listed — open the objective for details.
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
