import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { ContextFile } from '@/types/api'

export function useContextFiles() {
  return useQuery({
    queryKey: ['context-files'],
    queryFn: () => api.get<ContextFile[]>('/context/files'),
  })
}
