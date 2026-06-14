import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from './client'
import type { SquadFile, SquadSummary } from '../types'

export function useSquads() {
  return useQuery({
    queryKey: ['squads'],
    queryFn: () => apiFetch<SquadSummary[]>('/api/squads'),
  })
}

export function useSquad(name: string | null) {
  return useQuery({
    queryKey: ['squads', name],
    queryFn: () => apiFetch<SquadFile>(`/api/squads/${name}`),
    enabled: name != null,
  })
}

export function useSaveSquad() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ name, squad }: { name: string; squad: SquadFile }) =>
      apiFetch<{ name: string; path: string }>(`/api/squads/${name}`, {
        method: 'PUT',
        body: JSON.stringify(squad),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['squads'] }),
  })
}
