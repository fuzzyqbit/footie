import { useQuery } from '@tanstack/react-query'
import { apiFetch } from './client'
import type { ValueResponse } from '../types'

export interface ValueParams {
  min_ovr?: number
  max_price?: number
  min_price?: number
  stat?: string
  stat_min?: number
  pos?: string
  squad?: string
  league?: string
  nation?: string
  club?: string
  limit?: number
  per_tier?: number
}

function buildQs(params: ValueParams): string {
  const qs = new URLSearchParams()
  if (params.min_ovr != null) qs.set('min_ovr', String(params.min_ovr))
  if (params.max_price != null) qs.set('max_price', String(params.max_price))
  if (params.min_price != null) qs.set('min_price', String(params.min_price))
  if (params.stat && params.stat_min != null) {
    qs.set('stat', params.stat)
    qs.set('stat_min', String(params.stat_min))
  }
  if (params.pos) qs.set('pos', params.pos)
  if (params.squad) qs.set('squad', params.squad)
  if (params.league) qs.set('league', params.league)
  if (params.nation) qs.set('nation', params.nation)
  if (params.club) qs.set('club', params.club)
  if (params.limit != null) qs.set('limit', String(params.limit))
  if (params.per_tier != null) qs.set('per_tier', String(params.per_tier))
  const s = qs.toString()
  return s ? `?${s}` : ''
}

export function useValue(params: ValueParams = {}) {
  return useQuery({
    queryKey: ['value', params],
    queryFn: () => apiFetch<ValueResponse>(`/api/value${buildQs(params)}`),
  })
}
