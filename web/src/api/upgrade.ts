import { useMutation } from '@tanstack/react-query'
import { apiFetch } from './client'
import type { UpgradePlan, SquadFile } from '../types'

export interface UpgradeParams {
  squad: SquadFile
  budget: string
  swaps?: number
}

export function useUpgrade() {
  return useMutation({
    mutationFn: (params: UpgradeParams) =>
      apiFetch<UpgradePlan>('/api/upgrade', {
        method: 'POST',
        body: JSON.stringify(params),
      }),
  })
}
