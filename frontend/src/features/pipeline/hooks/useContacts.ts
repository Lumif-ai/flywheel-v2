import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { fetchContacts } from '../api'
import type { ContactParams } from '../types/pipeline'

export function useContacts(params: ContactParams) {
  const { enabled = true, ...queryParams } = params
  return useQuery({
    queryKey: ['contacts', queryParams],
    queryFn: () => fetchContacts(queryParams),
    staleTime: 30_000,
    placeholderData: keepPreviousData,
    enabled,
  })
}
