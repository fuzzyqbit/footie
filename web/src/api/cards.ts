import { useQuery } from '@tanstack/react-query'
import { apiFetch } from './client'
import type { CardListResponse } from '../types'

export interface CardParams {
  search?: string
  pos?: string
  version?: string
  league?: string
  nation?: string
  club?: string
  min_ovr?: number
  stat?: string
  stat_min?: number
  no_price?: boolean
  sort?: string
  limit?: number
  offset?: number
}

function buildQs(params: CardParams): string {
  const qs = new URLSearchParams()
  if (params.search) qs.set('search', params.search)
  if (params.pos) qs.set('pos', params.pos)
  if (params.version) qs.set('version', params.version)
  if (params.league) qs.set('league', params.league)
  if (params.nation) qs.set('nation', params.nation)
  if (params.club) qs.set('club', params.club)
  if (params.min_ovr != null) qs.set('min_ovr', String(params.min_ovr))
  if (params.stat && params.stat_min != null) {
    qs.set('stat', params.stat)
    qs.set('stat_min', String(params.stat_min))
  }
  if (params.no_price) qs.set('no_price', 'true')
  if (params.sort) qs.set('sort', params.sort)
  if (params.limit != null) qs.set('limit', String(params.limit))
  if (params.offset != null) qs.set('offset', String(params.offset))
  const s = qs.toString()
  return s ? `?${s}` : ''
}

export function useCards(params: CardParams = {}) {
  return useQuery({
    queryKey: ['cards', params],
    queryFn: () => apiFetch<CardListResponse>(`/api/cards${buildQs(params)}`),
  })
}

export function useAllCards() {
  // staleTime/gcTime come from the global QueryClient defaults (main.tsx).
  return useQuery({
    queryKey: ['cards', 'all'],
    queryFn: () => apiFetch<CardListResponse>('/api/cards?limit=5000'),
  })
}
