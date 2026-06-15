// Color a face-stat value (0-100) on a red -> yellow -> green ramp.
export function statColor(v: number | null): string {
  if (v == null) return '#2a2a3a' // border (no data)
  if (v >= 90) return '#16a34a' // green-600
  if (v >= 80) return '#4caf50' // chem green
  if (v >= 70) return '#eab308' // yellow-500
  if (v >= 60) return '#f97316' // orange-500
  return '#ef4444' // red-500
}

// Accent color for a card by rating tier (specials always read as gold).
export function tierColor(ovr: number, version: string): string {
  if (version.toLowerCase() !== 'base') return '#e2b714' // special = gold
  if (ovr >= 90) return '#e2b714' // gold
  if (ovr >= 83) return '#cbd5e1' // silver
  if (ovr >= 75) return '#d97706' // bronze
  return '#6b7280' // gray
}
