interface Props {
  // 6 face-stat values in display order; null renders as 0
  values: Array<number | null>
  size?: number
}

// Shape-only hexagonal radar of the six face stats. No text labels, so it can
// sit next to a labelled bar list without duplicating stat names.
export default function StatRadar({ values, size = 88 }: Props) {
  const r = size / 2
  const max = r - 6 // padding so vertex dots stay inside the viewbox
  const n = values.length
  const angle = (i: number) => (Math.PI * 2 * i) / n - Math.PI / 2
  const at = (i: number, radius: number): [number, number] => [
    r + Math.cos(angle(i)) * radius,
    r + Math.sin(angle(i)) * radius,
  ]
  const ring = (frac: number) =>
    values.map((_, i) => at(i, max * frac).join(',')).join(' ')
  const valuePoly = values
    .map((v, i) => at(i, max * ((v ?? 0) / 100)).join(','))
    .join(' ')

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      className="shrink-0"
      role="img"
      aria-label="Face stat radar"
    >
      {[0.33, 0.66, 1].map(frac => (
        <polygon
          key={frac}
          points={ring(frac)}
          fill="none"
          stroke="#2a2a3a"
          strokeWidth={1}
        />
      ))}
      {values.map((_, i) => {
        const [x, y] = at(i, max)
        return <line key={i} x1={r} y1={r} x2={x} y2={y} stroke="#2a2a3a" strokeWidth={1} />
      })}
      <polygon
        points={valuePoly}
        fill="#e2b714"
        fillOpacity={0.25}
        stroke="#e2b714"
        strokeWidth={1.5}
      />
      {values.map((v, i) => {
        const [x, y] = at(i, max * ((v ?? 0) / 100))
        return <circle key={i} cx={x} cy={y} r={1.6} fill="#e2b714" />
      })}
    </svg>
  )
}
