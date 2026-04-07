import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  fetchSavedViews,
  createSavedView,
  updateSavedView,
  deleteSavedView,
} from '../api'
import type { SavedView } from '../types/pipeline'

const SAVED_VIEWS_KEY = ['saved-views'] as const

export function useSavedViews() {
  return useQuery({
    queryKey: SAVED_VIEWS_KEY,
    queryFn: fetchSavedViews,
    staleTime: 60_000,
  })
}

export function useCreateSavedView() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createSavedView,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: SAVED_VIEWS_KEY })
    },
  })
}

export function useUpdateSavedView() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Parameters<typeof updateSavedView>[1] }) =>
      updateSavedView(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: SAVED_VIEWS_KEY })
    },
  })
}

export function useDeleteSavedView() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: deleteSavedView,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: SAVED_VIEWS_KEY })
    },
  })
}

/**
 * Build a URL path for a saved view by encoding its filters as search params.
 */
export function buildViewUrl(view: SavedView): string {
  const params = new URLSearchParams()
  const { filters } = view
  if (filters.stage?.length) params.set('stage', filters.stage.join(','))
  if (filters.fitTier?.length) params.set('fitTier', filters.fitTier.join(','))
  if (filters.relationshipType?.length) params.set('relationshipType', filters.relationshipType.join(','))
  if (filters.source) params.set('source', filters.source)
  if (filters.view && filters.view !== 'all') params.set('view', filters.view)
  if (filters.search) params.set('q', filters.search)
  const qs = params.toString()
  return qs ? `/pipeline?${qs}` : '/pipeline'
}
