import { useMutation } from '@tanstack/react-query'
import { apiFetch } from './client'
import type { BuildResult } from '../types'

export interface BuildParams {
  formation: string
  budget: string
  league?: string
  objective?: string
}

export function useBuild() {
  return useMutation({
    mutationFn: (params: BuildParams) =>
      apiFetch<BuildResult>('/api/build', {
        method: 'POST',
        body: JSON.stringify(params),
      }),
  })
}
