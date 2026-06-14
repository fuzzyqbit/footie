export default function SkeletonPitch() {
  const rows = [1, 4, 2, 3, 1]
  return (
    <div className="bg-pitch rounded-lg p-4 flex flex-col items-center justify-around gap-3 min-h-[360px] border border-[rgba(255,255,255,0.1)]">
      {rows.map((count, i) => (
        <div key={i} className="flex gap-2 justify-center">
          {Array.from({ length: count }).map((_, j) => (
            <div key={j} className="bg-card/50 rounded w-14 h-14 animate-pulse" />
          ))}
        </div>
      ))}
    </div>
  )
}
