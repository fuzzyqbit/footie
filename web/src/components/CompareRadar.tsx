export interface RadarSeries {
  label: string
  values: Array<number | null>
  color: string
}

interface Props {
  series: RadarSeries[]
  size?: number
}

// Overlays several face-stat polygons on one hexagonal grid for side-by-side
// comparison. Axis labels are drawn (PAC..PHY) since all series share them.
const AXIS_LABELS = ['PAC', 'SHO', 'PAS', 'DRI', 'DEF', 'PHY']

export default function CompareRadar({ series, size = 168 }: Props) {
  const r = size / 2
  const max = r - 18 // room for axis labels
  const n = AXIS_LABELS.length
  const angle = (i: number) => (Math.PI * 2 * i) / n - Math.PI / 2
  const at = (i: number, radius: number): [number, number] => [
    r + Math.cos(angle(i)) * radius,
    r + Math.sin(angle(i)) * radius,
  ]
  const ring = (frac: number) =>
    AXIS_LABELS.map((_, i) => at(i, max * frac).join(',')).join(' ')
  const poly = (values: Array<number | null>) =>
    AXIS_LABELS.map((_, i) => at(i, max * ((values[i] ?? 0) / 100)).join(',')).join(' ')

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      className="shrink-0"
      role="img"
      aria-label="Comparison radar"
    >
      {[0.33, 0.66, 1].map(frac => (
        <polygon key={frac} points={ring(frac)} fill="none" stroke="#2a2a3a" strokeWidth={1} />
      ))}
      {AXIS_LABELS.map((label, i) => {
        const [lx, ly] = at(i, max + 10)
        const [ex, ey] = at(i, max)
        return (
          <g key={label}>
            <line x1={r} y1={r} x2={ex} y2={ey} stroke="#2a2a3a" strokeWidth={1} />
            <text
              x={lx}
              y={ly}
              fontSize={9}
              fill="#aaaaaa"
              textAnchor="middle"
              dominantBaseline="middle"
            >
              {label}
            </text>
          </g>
        )
      })}
      {series.map(s => (
        <polygon
          key={s.label}
          points={poly(s.values)}
          fill={s.color}
          fillOpacity={0.12}
          stroke={s.color}
          strokeWidth={1.5}
        />
      ))}
    </svg>
  )
}
