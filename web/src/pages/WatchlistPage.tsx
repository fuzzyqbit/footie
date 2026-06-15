import { useWatchlist } from '../watchlist'
import CardTile from '../components/CardTile'

export default function WatchlistPage() {
  const cards = useWatchlist()
  const sorted = [...cards].sort((a, b) => b.ovr - a.ovr)

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-1">Watchlist</h1>
      <p className="text-muted text-sm mb-4">
        Players you flagged to look at later — tap the star on any card to add or remove it.
      </p>

      {sorted.length === 0 ? (
        <p className="text-muted text-sm">
          No flagged players yet. Tap the ☆ on any card to add it here.
        </p>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
          {sorted.map(card => (
            <CardTile key={card.id} card={card} />
          ))}
        </div>
      )}
    </div>
  )
}
