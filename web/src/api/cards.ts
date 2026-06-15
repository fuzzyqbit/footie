import { useQuery } from '@tanstack/react-query'
import { apiFetch } from './client'
import type { CardListResponse } from '../types'

export interface CardParams {
  search?: string
  pos?: string
  version?: string
  league?: string
  min_ovr?: number
  stat?: string
  stat_min?: number
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
  if (params.min_ovr != null) qs.set('min_ovr', String(params.min_ovr))
  if (params.stat && params.stat_min != null) {
    qs.set('stat', params.stat)
    qs.set('stat_min', String(params.stat_min))
  }
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
  return useQuery({
    queryKey: ['cards', 'all'],
    queryFn: () => apiFetch<CardListResponse>('/api/cards?limit=5000'),
    staleTime: 5 * 60 * 1000,
  })
}
