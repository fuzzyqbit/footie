import { useQuery } from '@tanstack/react-query'
import { apiFetch } from './client'
import type { Meta } from '../types'

export function useMeta() {
  return useQuery({
    queryKey: ['meta'],
    queryFn: () => apiFetch<Meta>('/api/meta'),
    staleTime: Infinity,
  })
}
