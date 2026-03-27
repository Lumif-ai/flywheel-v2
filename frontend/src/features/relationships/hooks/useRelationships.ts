import { useQuery } from '@tanstack/react-query'
import { useAuthStore } from '@/stores/auth'
import { fetchRelationships, queryKeys } from '../api'

export function useRelationships(type: string) {
  const user = useAuthStore((s) => s.user)

  return useQuery({
    queryKey: queryKeys.relationships.list(type),
    queryFn: () => fetchRelationships(type),
    enabled: !!user,
  })
}
