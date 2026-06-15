import { useUpdates } from '../api/updates'
import CardTile from '../components/CardTile'
import SkeletonGrid from '../components/SkeletonGrid'

export default function UpdatesPage() {
  const { data, isPending, error } = useUpdates()

  const refreshedAt = data?.refreshed_at
    ? new Date(data.refreshed_at).toLocaleString()
    : 'Never refreshed'
  const newCards = data?.new_cards ?? []

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-1">Latest</h1>
      <p className="text-muted text-sm mb-4">{refreshedAt}</p>

      {error && (
        <div className="text-red-400 bg-red-900/20 border border-red-800 rounded p-3 mb-4">
          {error.message}
        </div>
      )}

      {data && (
        <p className="text-muted text-sm mb-3">
          {data.new_count} new cards, {data.updated_count} updated
        </p>
      )}

      {isPending ? (
        <SkeletonGrid />
      ) : newCards.length === 0 ? (
        <p className="text-muted text-sm">No new cards from the last refresh.</p>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
          {newCards.map(card => (
            <CardTile key={card.id} card={card} />
          ))}
        </div>
      )}
    </div>
  )
}
