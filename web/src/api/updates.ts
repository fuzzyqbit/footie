import { useQuery } from '@tanstack/react-query'
import { apiFetch } from './client'
import type { UpdateInfo } from '../types'

export function useUpdates() {
  return useQuery({
    queryKey: ['updates'],
    queryFn: () => apiFetch<UpdateInfo>('/api/updates'),
  })
}
