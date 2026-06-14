import { useMutation } from '@tanstack/react-query'
import { apiFetch } from './client'
import type { ChemReport, SquadFile } from '../types'

export function useChem() {
  return useMutation({
    mutationFn: (squad: SquadFile) =>
      apiFetch<ChemReport>('/api/chem', {
        method: 'POST',
        body: JSON.stringify(squad),
      }),
  })
}
