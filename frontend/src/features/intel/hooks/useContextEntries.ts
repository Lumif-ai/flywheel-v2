import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { PaginatedResponse, ContextEntry } from '@/types/api'

export interface EntryFilters {
  file_name: string
  search?: string
  offset: number
  limit: number
}

export function useContextEntries(filters: EntryFilters | null) {
  return useQuery({
    queryKey: ['context-entries', filters],
    queryFn: () =>
      api.get<PaginatedResponse<ContextEntry>>('/context/entries', {
        params: {
          file_name: filters!.file_name,
          offset: filters!.offset,
          limit: filters!.limit,
          search: filters!.search || undefined,
        },
      }),
    enabled: !!filters?.file_name,
    placeholderData: keepPreviousData,
  })
}
