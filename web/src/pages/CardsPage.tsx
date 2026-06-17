import { useState } from 'react'
import { useCards, type CardParams } from '../api/cards'
import CardTile from '../components/CardTile'
import SearchFilterBar from '../components/SearchFilterBar'
import SkeletonGrid from '../components/SkeletonGrid'

const LIMIT = 50

export default function CardsPage() {
  const [params, setParams] = useState<CardParams>({ limit: LIMIT, offset: 0, sort: 'ovr' })
  const { data, isPending, error } = useCards(params)

  const offset = params.offset ?? 0
  const total = data?.total ?? 0
  const page = Math.floor(offset / LIMIT) + 1
  const totalPages = Math.ceil(total / LIMIT)

  return (
    <div>
      <h1 className="text-2xl font-bold text-fg mb-4">Cards</h1>
      <SearchFilterBar params={params} onChange={p => setParams({ ...p, limit: LIMIT })} />

      {error && (
        <div className="text-red-400 bg-red-900/20 border border-red-800 rounded p-3 mb-4">
          {error.message}
        </div>
      )}

      {data && (
        <p className="text-muted text-sm mb-3">{total} cards</p>
      )}

      {isPending ? (
        <SkeletonGrid />
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
          {(data?.cards ?? []).map(card => (
            <CardTile key={card.id} card={card} />
          ))}
        </div>
      )}

      {data && (
        <div className="flex items-center gap-3 mt-4">
          <button
            onClick={() => setParams(p => ({ ...p, offset: Math.max(0, (p.offset ?? 0) - LIMIT) }))}
            disabled={offset === 0}
            className="px-3 py-1.5 bg-card border border-border rounded text-sm text-fg disabled:opacity-40"
          >
            Prev
          </button>
          <span className="text-muted text-sm">{page} / {totalPages || 1}</span>
          <button
            onClick={() => setParams(p => ({ ...p, offset: (p.offset ?? 0) + LIMIT }))}
            disabled={offset + LIMIT >= total}
            className="px-3 py-1.5 bg-card border border-border rounded text-sm text-fg disabled:opacity-40"
          >
            Next
          </button>
        </div>
      )}
    </div>
  )
}
