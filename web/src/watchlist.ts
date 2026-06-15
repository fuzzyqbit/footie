import { useSyncExternalStore } from 'react'
import type { Card } from './types'

const KEY = 'fc26:watchlist'

function read(): Record<string, Card> {
  try {
    const raw = localStorage.getItem(KEY)
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}

let cache = read()
const listeners = new Set<() => void>()

function emit() {
  listeners.forEach(l => l())
}

function write(next: Record<string, Card>) {
  cache = next
  try {
    localStorage.setItem(KEY, JSON.stringify(next))
  } catch {
    // storage full or unavailable — keep in-memory cache
  }
  emit()
}

export function toggleWatch(card: Card) {
  const next = { ...cache }
  if (next[card.id]) delete next[card.id]
  else next[card.id] = card
  write(next)
}

export function removeWatch(id: string) {
  if (!cache[id]) return
  const next = { ...cache }
  delete next[id]
  write(next)
}

export function clearWatchlist() {
  write({})
}

function subscribe(cb: () => void) {
  listeners.add(cb)
  return () => {
    listeners.delete(cb)
  }
}

// keep other tabs in sync
if (typeof window !== 'undefined') {
  window.addEventListener('storage', e => {
    if (e.key === KEY) {
      cache = read()
      emit()
    }
  })
}

export function useWatchlist(): Card[] {
  const map = useSyncExternalStore(subscribe, () => cache, () => cache)
  return Object.values(map)
}

export function useIsWatched(id: string): boolean {
  return useSyncExternalStore(
    subscribe,
    () => cache[id] != null,
    () => cache[id] != null,
  )
}
