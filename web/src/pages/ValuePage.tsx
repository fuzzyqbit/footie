import { useValue } from '../api/value'
import CardTile from '../components/CardTile'
import SkeletonGrid from '../components/SkeletonGrid'

export default function ValuePage() {
  const { data, isPending, error } = useValue({ per_tier: 1 })
  const picks = data?.picks ?? []

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-1">Value</h1>
      <p className="text-muted text-sm mb-4">
        Best bargain at each rating tier — cheap, underrated cards by rating-per-coin.
      </p>

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
