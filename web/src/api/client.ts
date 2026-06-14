const BASE = 'http://localhost:8026'

interface Envelope<T> {
  ok: boolean
  data: T | null
  error: string | null
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  const json: Envelope<T> = await res.json()
  if (!json.ok) throw new Error(json.error ?? 'API error')
  return json.data as T
}
